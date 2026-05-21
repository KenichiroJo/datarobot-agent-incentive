"""手数料計算エージェントの LangGraph 実装。

6 ノードの実行フロー:
  START → supervisor → data_parser → calculator → hitl_review
                                          ↓ (interrupt)
                                       approve → explainer → END
  supervisor → explainer → END (説明要求時)

HITL は ``langgraph.types.interrupt`` を使う。再開時は ``Command(resume=decisions)`` を
graph.invoke / astream の 1 引数として渡す。
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.commission_engine.anomaly_detector import detect_anomalies
from app.commission_engine.commission_calculator import calculate_commission
from app.commission_engine.excel_parser import parse_master_excel, parse_sales_excel
from app.commission_engine.report_generator import generate_summary
from app.commission_engine.state import CommissionState

# モジュールレベルで checkpointer を保持してセッション復元に使う
_memory = MemorySaver()


def get_checkpointer() -> MemorySaver:
    """FastAPI 側から checkpointer を共有するためのアクセサ。"""
    return _memory


SUPERVISOR_SYSTEM_PROMPT = """あなたは販売管理手数料計算エージェントのスーパーバイザーです。
ユーザのメッセージと現在の State をもとに、次にどのノードへルーティングするか決定してください。

選択肢:
- "data_parser": ファイルがアップロード済みで、計算指示がある場合
- "explainer": 計算結果について「説明して」「根拠を教えて」と問われた場合
- "END": 通常のチャット応答で十分な場合

応答は次のノード名のみを 1 単語で返してください (data_parser / explainer / END)。
"""


def _detect_file_type(filename: str) -> str:
    """ファイル名から種別判定。"""
    if "売上明細" in filename or "売上" in filename:
        return "sales"
    if "取引条件" in filename or "マスタ" in filename:
        return "master"
    return "unknown"


def supervisor_node_factory(llm: BaseChatModel):
    """LLM を使ったルーティングノード。"""

    def supervisor(state: CommissionState) -> dict[str, Any]:
        messages = state.get("messages", [])
        if not messages:
            return {"next_route": "END"}

        # 既に計算結果がある + メッセージに「説明」キーワード
        last_user = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                last_user = (
                    m.content if isinstance(m.content, str) else str(m.content)
                )
                break

        # シンプルなキーワードルーティング (LLM 呼び出しコスト削減)
        if state.get("calculation_results") and (
            "説明" in last_user or "根拠" in last_user or "なぜ" in last_user
        ):
            return {"next_route": "explainer"}

        if state.get("uploaded_files") and not state.get("calculation_results"):
            return {"next_route": "data_parser"}

        # 上記いずれでもなければ LLM に判断させる
        try:
            ai = llm.invoke(
                [
                    SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
                    HumanMessage(
                        content=f"User message: {last_user}\n"
                        f"State summary: uploaded_files={len(state.get('uploaded_files', []) or [])}, "
                        f"results={len(state.get('calculation_results', []) or [])}, "
                        f"hitl_pending={len(state.get('pending_hitl', []) or [])}"
                    ),
                ]
            )
            decision = (
                ai.content if isinstance(ai.content, str) else str(ai.content)
            ).strip()
            for opt in ("data_parser", "explainer", "END"):
                if opt in decision:
                    return {"next_route": opt}
        except Exception as e:
            return {
                "next_route": "END",
                "error_message": f"supervisor LLM error: {e}",
            }
        return {"next_route": "END"}

    return supervisor


def data_parser_node(state: CommissionState) -> dict[str, Any]:
    """アップロードファイルをパースして state.sales_records / master_records を埋める。"""
    files = state.get("uploaded_files") or []
    sales_records: list[dict] = []
    master_records: dict[str, dict] = {}
    msgs: list[str] = []

    for f in files:
        path = f.get("path")
        filename = f.get("filename", "")
        detected = f.get("detected_type") or _detect_file_type(filename)
        if not path:
            continue
        try:
            if detected == "sales":
                parsed = parse_sales_excel(path)
                sales_records.extend(parsed)
                msgs.append(f"売上明細 {filename}: {len(parsed)} 行")
            elif detected == "master":
                parsed_m = parse_master_excel(path)
                master_records.update(parsed_m)
                msgs.append(f"取引条件マスタ {filename}: {len(parsed_m)} 件")
            else:
                msgs.append(f"未判定ファイル {filename}: スキップ")
        except Exception as e:
            return {
                "processing_status": "error",
                "error_message": f"{filename} パース失敗: {e}",
            }

    summary_text = "データパース完了: " + " / ".join(msgs)
    return {
        "sales_records": sales_records,
        "master_records": master_records,
        "processing_status": "calculating",
        "messages": [AIMessage(content=summary_text)],
    }


def calculator_node(state: CommissionState) -> dict[str, Any]:
    """全売上明細に手数料計算を適用しサマリも生成する。"""
    sales = state.get("sales_records") or []
    master = state.get("master_records") or {}
    if not sales:
        return {
            "processing_status": "error",
            "error_message": "計算対象の売上明細がありません",
        }

    results = [calculate_commission(rec, master) for rec in sales]
    pending = detect_anomalies(results, threshold=100_000)
    summary = generate_summary(results)

    msg = (
        f"計算完了: 全 {summary['total_records']} 件 / "
        f"自動完了 {summary['auto_completed']} 件 / "
        f"HITL対象 {summary['hitl_pending']} 件 / "
        f"合計手数料 {summary['total_commission_amount']:,} 円"
    )
    return {
        "calculation_results": results,
        "pending_hitl": pending,
        "summary": summary,
        "processing_status": "review" if pending else "approved",
        "messages": [AIMessage(content=msg)],
    }


def hitl_review_node(state: CommissionState) -> dict[str, Any]:
    """HITL 承認待ち。LangGraph interrupt で停止し、再開時に decisions を受け取る。"""
    pending = state.get("pending_hitl") or []
    if not pending:
        return {"user_decisions": [], "processing_status": "approved"}

    payload = {
        "type": "hitl_review",
        "pending_count": len(pending),
        "pending_summary": [
            {
                "record_no": p.get("record_no"),
                "partner_name": p.get("partner_name"),
                "product": p.get("product"),
                "total_commission": p.get("total_commission"),
                "hitl_reason": p.get("hitl_reason"),
            }
            for p in pending[:50]
        ],
    }
    decisions = interrupt(payload)
    return {
        "user_decisions": decisions if isinstance(decisions, list) else [],
    }


def approve_node(state: CommissionState) -> dict[str, Any]:
    """承認結果を反映して approved_results を確定する。"""
    results = state.get("calculation_results") or []
    decisions = {
        d["record_no"]: d for d in (state.get("user_decisions") or []) if "record_no" in d
    }

    approved: list[dict] = []
    for r in results:
        rn = r.get("record_no")
        d = decisions.get(rn)
        if r.get("is_anomaly"):
            if not d:
                # 未承認の異常レコードは除外
                continue
            action = d.get("action")
            if action == "approve":
                approved.append(r)
            elif action == "manual":
                manual_amount = d.get("manual_amount")
                if manual_amount is not None:
                    r2 = dict(r)
                    r2["total_commission"] = int(manual_amount)
                    r2["is_anomaly"] = False
                    r2["hitl_reason"] = (
                        f"手動入力: {manual_amount} 円 (元: {r.get('total_commission')})"
                    )
                    approved.append(r2)
            # "reject" の場合は approved に追加しない
        else:
            approved.append(r)

    return {
        "approved_results": approved,
        "processing_status": "approved",
        "messages": [
            AIMessage(
                content=f"承認確定: {len(approved)} 件を確定データに反映しました。CSV エクスポート可能です。"
            )
        ],
    }


def explainer_node_factory(llm: BaseChatModel):
    """LLM で計算根拠を日本語で説明するノード（ストリーミング対応）。"""

    def explainer(state: CommissionState) -> dict[str, Any]:
        target = state.get("explain_record_no")
        results = state.get("calculation_results") or []
        record = None
        if target is not None:
            record = next(
                (r for r in results if r.get("record_no") == target), None
            )

        if record is None:
            # 最後のメッセージから対象 record_no を推測（数字抽出）
            messages = state.get("messages", [])
            if messages:
                last = (
                    messages[-1].content
                    if isinstance(messages[-1].content, str)
                    else str(messages[-1].content)
                )
                import re

                m = re.search(r"(\d{3,})", last)
                if m and results:
                    candidate = int(m.group(1))
                    record = next(
                        (r for r in results if r.get("record_no") == candidate),
                        None,
                    )

        if record is None:
            return {
                "messages": [
                    AIMessage(
                        content="説明対象のレコードが見つかりませんでした。レコード番号を指定してください。"
                    )
                ],
                "processing_status": "explained",
            }

        trace_text = "\n".join(record.get("calculation_trace", []))
        prompt = (
            "あなたは手数料計算の説明アシスタントです。以下の計算トレースをもとに、"
            "ユーザに対して計算根拠を 200 字程度の日本語でわかりやすく説明してください。\n"
            "\n"
            f"対象レコード No: {record.get('record_no')}\n"
            f"取引先: {record.get('partner_name')}\n"
            f"商材: {record.get('product')}\n"
            f"合計手数料: {record.get('total_commission')} 円\n"
            "\n"
            f"計算トレース:\n{trace_text}\n"
        )
        try:
            ai = llm.invoke([HumanMessage(content=prompt)])
            content = (
                ai.content if isinstance(ai.content, str) else str(ai.content)
            )
            return {
                "messages": [AIMessage(content=content)],
                "processing_status": "explained",
            }
        except Exception as e:
            return {
                "messages": [AIMessage(content=f"説明生成失敗: {e}")],
                "processing_status": "error",
                "error_message": str(e),
            }

    return explainer


def _route_after_supervisor(state: CommissionState) -> str:
    return state.get("next_route") or "END"


def _route_after_calculator(state: CommissionState) -> str:
    if state.get("pending_hitl"):
        return "hitl_review"
    return "approve"


def commission_graph_factory(
    llm: BaseChatModel,
    tools: list | None = None,
    verbose: bool = False,
):
    """手数料計算グラフを組み立てて返す。

    Returns:
        コンパイル済み StateGraph (with MemorySaver checkpointer)
    """
    g: StateGraph[CommissionState] = StateGraph(CommissionState)

    g.add_node("supervisor", supervisor_node_factory(llm))
    g.add_node("data_parser", data_parser_node)
    g.add_node("calculator", calculator_node)
    g.add_node("hitl_review", hitl_review_node)
    g.add_node("approve", approve_node)
    g.add_node("explainer", explainer_node_factory(llm))

    g.add_edge(START, "supervisor")
    g.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {
            "data_parser": "data_parser",
            "explainer": "explainer",
            "END": END,
        },
    )
    g.add_edge("data_parser", "calculator")
    g.add_conditional_edges(
        "calculator",
        _route_after_calculator,
        {"hitl_review": "hitl_review", "approve": "approve"},
    )
    g.add_edge("hitl_review", "approve")
    g.add_edge("approve", "explainer")
    g.add_edge("explainer", END)

    return g.compile(checkpointer=_memory)


def build_commission_graph(llm: BaseChatModel | None = None):
    """シンプルなビルダー: LLM が未指定なら get_llm() を使う。"""
    if llm is None:
        from datarobot_genai.langgraph.llm import get_llm

        llm = get_llm(model_name=None)
    return commission_graph_factory(llm, tools=[])


__all__ = [
    "CommissionState",
    "Command",
    "build_commission_graph",
    "commission_graph_factory",
    "get_checkpointer",
]
