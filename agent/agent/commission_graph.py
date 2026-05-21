# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""コミッション計算ワークフロー — LangGraph グラフ定義。

6 ノード構成:
1. supervisor   (LLM)     : ユーザーメッセージから次のノードをルーティング
2. data_parser  (no LLM)  : uploaded_files を走査してパース
3. calculator   (no LLM)  : sales_records を全件計算
4. hitl_review  (interrupt前で停止) : HITL 承認待ち
5. approve      (no LLM)  : 承認結果をマージして確定
6. explainer    (LLM)     : 計算根拠をストリーミングで日本語説明

このモジュールは **未コンパイルの StateGraph** を返す。
コンパイル（MemorySaver / interrupt_before 付与）は FastAPI 側で行う。
これは ``datarobot_agent_class_from_langgraph`` のパターンに従いつつ、
HITL を成立させるために FastAPI プロセスで graph を所有する設計のため。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph

try:
    # 通常の package import パス
    from agent.agent.state import (  # type: ignore
        ROUTE_APPROVE,
        ROUTE_CALCULATE,
        ROUTE_END,
        ROUTE_EXPLAIN,
        ROUTE_PARSE,
        ROUTE_REVIEW,
        STATUS_APPROVING,
        STATUS_AWAITING_HITL,
        STATUS_CALCULATING,
        STATUS_DONE,
        STATUS_ERROR,
        STATUS_EXPLAINING,
        STATUS_PARSING,
        CommissionState,
    )
    from agent.agent.tools.anomaly_detector import detect_anomalies  # type: ignore
    from agent.agent.tools.commission_calculator import (  # type: ignore
        DEFAULT_HIGH_AMOUNT_THRESHOLD,
        calculate_commission,
    )
    from agent.agent.tools.excel_parser import (  # type: ignore
        parse_master_excel,
        parse_sales_excel,
    )
    from agent.agent.tools.report_generator import generate_summary  # type: ignore
except ImportError:
    # 直接 tools/ を sys.path に入れた場合の fallback (smoke test 用)
    from anomaly_detector import detect_anomalies  # type: ignore
    from commission_calculator import (  # type: ignore
        DEFAULT_HIGH_AMOUNT_THRESHOLD,
        calculate_commission,
    )
    from excel_parser import parse_master_excel, parse_sales_excel  # type: ignore
    from report_generator import generate_summary  # type: ignore
    from state import (  # type: ignore
        ROUTE_APPROVE,
        ROUTE_CALCULATE,
        ROUTE_END,
        ROUTE_EXPLAIN,
        ROUTE_PARSE,
        ROUTE_REVIEW,
        STATUS_APPROVING,
        STATUS_AWAITING_HITL,
        STATUS_CALCULATING,
        STATUS_DONE,
        STATUS_ERROR,
        STATUS_EXPLAINING,
        STATUS_PARSING,
        CommissionState,
    )

logger = logging.getLogger(__name__)


# ============================================================
# Prompt template
# ============================================================
# LangGraphAgent.convert_input_message から渡される {topic} 変数を受ける。
# commission ワークフローではユーザー入力を素直にメッセージ化するだけで良い。
commission_prompt_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "あなたは販売管理手数料計算ワークフローのアシスタントです。"
            "ユーザーの指示に応じて、ファイルのパース・手数料計算・HITL レビュー誘導・"
            "計算根拠の説明のいずれかを行います。",
        ),
        ("user", "{topic}"),
    ]
)


# ============================================================
# Supervisor 用システムプロンプト
# ============================================================
_SUPERVISOR_SYSTEM = """あなたはコミッション計算ワークフローのスーパーバイザーです。

ユーザーのメッセージと現在のワークフロー状態から、次に実行すべきフェーズを判断してください。

[次フェーズの候補]
- "parse"     : アップロード済みファイルをパースする
- "calculate" : パース済みデータで手数料を計算する
- "review"    : HITL レビュー画面に誘導する（実際には interrupt で停止）
- "approve"   : HITL の承認結果を反映する
- "explain"   : 計算根拠を説明する
- "end"       : 何もせず終了（雑談・無関係な質問）

[出力フォーマット]
必ず以下の JSON のみを返してください。説明文や前置きは一切不要です:

{"route": "<選択肢の一つ>", "reason": "<日本語で短く>"}
"""


# ============================================================
# Plain Python ノード
# ============================================================


def _node_data_parser(state: CommissionState) -> dict[str, Any]:
    """uploaded_files を走査してパース。detected_type で売上 / マスタを振り分ける。"""
    uploaded = state.get("uploaded_files", []) or []
    sales: list[dict[str, Any]] = list(state.get("sales_records", []) or [])
    master: dict[str, dict[str, Any]] = dict(state.get("master_records", {}) or {})

    parsed_summary: list[str] = []
    for f in uploaded:
        path = f.get("path")
        dtype = f.get("detected_type")
        filename = f.get("filename") or path
        if not path:
            continue
        try:
            if dtype == "sales":
                parsed = parse_sales_excel(path)
                sales.extend(parsed)
                parsed_summary.append(f"売上明細 {filename} → {len(parsed)} 件")
            elif dtype == "master":
                parsed = parse_master_excel(path)
                master.update(parsed)
                parsed_summary.append(f"取引条件マスタ {filename} → {len(parsed)} キー")
            else:
                logger.warning("不明な detected_type=%r path=%s", dtype, path)
                parsed_summary.append(f"未判定 {filename} → スキップ")
        except Exception as exc:  # noqa: BLE001
            logger.exception("パース失敗 path=%s", path)
            parsed_summary.append(f"{filename} のパースに失敗: {exc}")
            return {
                "processing_status": STATUS_ERROR,
                "error_message": f"{filename} のパースに失敗: {exc}",
                "messages": [AIMessage(content=f"❌ {filename} のパース中にエラー: {exc}")],
            }

    msg = (
        "ファイルパース完了:\n  - " + "\n  - ".join(parsed_summary)
        if parsed_summary
        else "パース対象ファイルがありません。"
    )
    return {
        "sales_records": sales,
        "master_records": master,
        "processing_status": STATUS_CALCULATING,
        "error_message": None,
        "messages": [AIMessage(content=msg)],
    }


def _node_calculator(state: CommissionState) -> dict[str, Any]:
    """sales_records を全件計算し、HITL 候補を抽出する。"""
    sales = state.get("sales_records", []) or []
    master = state.get("master_records", {}) or {}
    threshold = state.get("anomaly_threshold") or DEFAULT_HIGH_AMOUNT_THRESHOLD

    if not sales:
        return {
            "processing_status": STATUS_ERROR,
            "error_message": "売上明細が空です。先にファイルをアップロードしてください。",
            "messages": [AIMessage(content="❌ 売上明細が空のため計算できません。")],
        }

    results = [calculate_commission(rec, master, high_amount_threshold=threshold) for rec in sales]
    flagged = detect_anomalies(results, threshold=threshold)
    summary = generate_summary(results)

    next_status = STATUS_AWAITING_HITL if flagged else STATUS_DONE
    kpi = summary["kpi"]
    msg = (
        f"計算完了: 全 {kpi['total_records']} 件 / 自動完了 {kpi['auto_completed']} 件 / "
        f"HITL 残 {kpi['hitl_pending']} 件 / 合計 ¥{kpi['total_commission_amount']:,}"
    )
    return {
        "calculation_results": results,
        "pending_hitl": flagged,
        "summary": summary,
        "processing_status": next_status,
        "messages": [AIMessage(content=msg)],
    }


def _node_hitl_review(state: CommissionState) -> dict[str, Any]:
    """HITL レビュー用のパススルーノード。

    compile 時に ``interrupt_before=["hitl_review"]`` が指定されているため、
    実際にはこのノード "前" でグラフが停止する。resume されてからこのノードが走り、
    processing_status を ``approving`` に進める。
    """
    pending = state.get("pending_hitl", []) or []
    return {
        "processing_status": STATUS_APPROVING,
        "messages": [
            AIMessage(content=f"HITL レビュー再開: {len(pending)} 件の承認待ちを処理します。")
        ],
    }


def _node_approve(state: CommissionState) -> dict[str, Any]:
    """承認/却下/手動入力の決定を calculation_results にマージし approved_results を確定する。"""
    results = list(state.get("calculation_results", []) or [])
    pending = state.get("pending_hitl", []) or []

    # pending には事前に FastAPI 側で hitl_decided / hitl_action / manual_amount が
    # セットされている想定（hitl/approve エンドポイントが state を update してから resume する）。
    decisions_by_no = {p.get("record_no"): p for p in pending if p.get("hitl_decided")}

    approved: list[dict[str, Any]] = []
    for r in results:
        rno = r.get("record_no")
        if rno in decisions_by_no:
            d = decisions_by_no[rno]
            action = d.get("hitl_action")
            if action == "approve":
                approved.append({**r, "hitl_decided": True, "hitl_action": "approve", "status": "hitl_approved"})
            elif action == "manual":
                approved.append(
                    {
                        **r,
                        "hitl_decided": True,
                        "hitl_action": "manual",
                        "total_commission": d.get("manual_amount", r.get("total_commission")),
                        "status": "manual",
                    }
                )
            elif action == "reject":
                # rejected は approved_results に含めない
                continue
        elif r.get("master_found") and not r.get("is_anomaly"):
            # 元から HITL 対象外のレコードはそのまま自動承認
            approved.append({**r, "status": r.get("status", "ok")})

    # 集計を再計算
    summary = generate_summary(approved)
    msg = (
        f"確定: {len(approved)} 件 / 合計 ¥{summary['kpi']['total_commission_amount']:,}"
    )
    return {
        "approved_results": approved,
        "summary": summary,
        "processing_status": STATUS_EXPLAINING,
        "messages": [AIMessage(content=msg)],
    }


# ============================================================
# LLM ノード
# ============================================================


def _make_supervisor_node(llm: BaseChatModel):  # type: ignore[no-untyped-def]
    """LLM を呼んでルーティング判断する supervisor ノードを生成。"""

    async def _node(state: CommissionState) -> dict[str, Any]:
        last_user = ""
        for m in reversed(state.get("messages", []) or []):
            if isinstance(m, HumanMessage):
                last_user = str(m.content)
                break

        ctx = (
            f"現在のステータス: {state.get('processing_status', 'idle')}\n"
            f"パース済み売上行数: {len(state.get('sales_records', []) or [])}\n"
            f"マスタキー数: {len(state.get('master_records', {}) or {})}\n"
            f"計算結果件数: {len(state.get('calculation_results', []) or [])}\n"
            f"HITL 承認待ち: {len(state.get('pending_hitl', []) or [])}\n"
        )
        prompt = [
            SystemMessage(content=_SUPERVISOR_SYSTEM),
            HumanMessage(content=f"[ワークフロー状態]\n{ctx}\n[ユーザーメッセージ]\n{last_user}"),
        ]
        try:
            resp = await llm.ainvoke(prompt)
            content = str(resp.content).strip()
            route, reason = _parse_route_json(content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("supervisor LLM call failed: %s — fallback to heuristic", exc)
            route, reason = _heuristic_route(state, last_user), "LLM 呼び出し失敗のためヒューリスティック判定"

        logger.info("supervisor route=%s reason=%s", route, reason)
        return {
            "next_node_hint": route,
            "messages": [AIMessage(content=f"次のフェーズ: {route} ({reason})")],
        }

    return _node


def _parse_route_json(content: str) -> tuple[str, str]:
    """LLM 出力から ``{"route": ..., "reason": ...}`` を抽出。失敗時は (end, ...) を返す。"""
    # コードブロックを剥がす
    cleaned = re.sub(r"```(?:json)?\s*", "", content).replace("```", "").strip()
    # 最初の JSON オブジェクトを抜き出す
    match = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
    if not match:
        return ROUTE_END, f"JSON 抽出失敗: {content[:60]}"
    try:
        obj = json.loads(match.group(0))
        route = obj.get("route", ROUTE_END)
        if route not in {ROUTE_PARSE, ROUTE_CALCULATE, ROUTE_REVIEW, ROUTE_APPROVE, ROUTE_EXPLAIN, ROUTE_END}:
            return ROUTE_END, f"未知のルート: {route}"
        return route, str(obj.get("reason", ""))
    except json.JSONDecodeError as exc:
        return ROUTE_END, f"JSON parse 失敗: {exc}"


def _heuristic_route(state: CommissionState, user_text: str) -> str:
    """LLM 不調時のフォールバック簡易ルーティング。"""
    text = (user_text or "").lower()
    if "説明" in user_text or "explain" in text or "根拠" in user_text:
        return ROUTE_EXPLAIN
    if state.get("processing_status") == STATUS_AWAITING_HITL:
        return ROUTE_REVIEW
    if state.get("uploaded_files") and not state.get("sales_records"):
        return ROUTE_PARSE
    if state.get("sales_records") and not state.get("calculation_results"):
        return ROUTE_CALCULATE
    return ROUTE_END


def _make_explainer_node(llm: BaseChatModel):  # type: ignore[no-untyped-def]
    """指定レコードの calculation_trace を LLM が日本語で要約説明する。

    LLM 呼び出しは ``astream`` 経由でトークン単位に流れる前提（FastAPI 側で
    stream_mode='messages' を購読すれば自動で SSE に乗る）。
    """

    async def _node(state: CommissionState) -> dict[str, Any]:
        last_user = ""
        for m in reversed(state.get("messages", []) or []):
            if isinstance(m, HumanMessage):
                last_user = str(m.content)
                break

        # ユーザーメッセージから record_no を抽出（"レコード 12345 の…" / "record_no 12345" など）
        target_no: int | None = None
        m = re.search(r"\d{3,}", last_user)
        if m:
            try:
                target_no = int(m.group(0))
            except ValueError:
                target_no = None

        results = state.get("calculation_results", []) or []
        if target_no is None:
            target_record = results[0] if results else None
        else:
            target_record = next((r for r in results if r.get("record_no") == target_no), None)

        if not target_record:
            ai = AIMessage(content="該当レコードが見つかりませんでした。レコード番号を確認してください。")
            return {"messages": [ai], "processing_status": STATUS_DONE}

        trace_lines = target_record.get("calculation_trace", []) or []
        trace_text = "\n".join(f"- {t}" for t in trace_lines)
        system_prompt = (
            "あなたは販売管理手数料計算のアシスタントです。提示された計算根拠 (calculation_trace) を読み、"
            "なぜこの金額になったかを 4〜6 文の日本語で簡潔に説明してください。専門用語は最小限に。"
        )
        user_prompt = (
            f"レコード番号 {target_record.get('record_no')} / 取引先 {target_record.get('取引先名称')} / "
            f"商材 {target_record.get('商材')} / 決済 {target_record.get('決済方法')} / "
            f"合計 {target_record.get('total_commission')} 円\n\n"
            f"計算根拠:\n{trace_text}"
        )
        # LangGraph の stream_mode='messages' が AIMessageChunk を捕捉できるよう、
        # ノードからは「最終 AIMessage」を返す。LLM 側で streaming 経由のトークン配信は
        # FastAPI の compiled_graph.astream(stream_mode=['messages']) で行う。
        resp = await llm.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
        return {
            "messages": [AIMessage(content=str(resp.content))],
            "processing_status": STATUS_DONE,
        }

    return _node


# ============================================================
# Conditional edge
# ============================================================


def _route_from_supervisor(state: CommissionState) -> str:
    """supervisor が next_node_hint にセットしたルートを返す。"""
    hint = state.get("next_node_hint") or ROUTE_END
    return hint


# ============================================================
# Graph factory (template 契約に従う)
# ============================================================


def commission_graph_factory(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,  # noqa: ARG001 (commission graph は MCP/外部 tools 未使用)
    verbose: bool = False,
) -> StateGraph:
    """コミッション計算ワークフローの未コンパイル StateGraph を返す。

    FastAPI 側で ``workflow.compile(checkpointer=MemorySaver(), interrupt_before=["hitl_review"])``
    することで HITL を実現する。
    """
    workflow: StateGraph = StateGraph(CommissionState)

    workflow.add_node("supervisor", _make_supervisor_node(llm))
    workflow.add_node("data_parser", _node_data_parser)
    workflow.add_node("calculator", _node_calculator)
    workflow.add_node("hitl_review", _node_hitl_review)
    workflow.add_node("approve", _node_approve)
    workflow.add_node("explainer", _make_explainer_node(llm))

    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        _route_from_supervisor,
        {
            ROUTE_PARSE: "data_parser",
            ROUTE_CALCULATE: "calculator",
            ROUTE_REVIEW: "hitl_review",
            ROUTE_APPROVE: "approve",
            ROUTE_EXPLAIN: "explainer",
            ROUTE_END: END,
        },
    )
    # 線形フロー: parser → calculator → hitl_review → approve → END
    # (explainer は別経路で END へ)
    workflow.add_edge("data_parser", "calculator")
    workflow.add_edge("calculator", "hitl_review")
    workflow.add_edge("hitl_review", "approve")
    workflow.add_edge("approve", END)
    workflow.add_edge("explainer", END)

    if verbose:
        logger.info("commission_graph_factory: graph built with 6 nodes")

    return workflow
