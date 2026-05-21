"""LangGraph 呼び出しをラップし、SSE イベント列に変換する。

handler は ``agent.commission.graph.build_commission_graph()`` を遅延 import する。
これによりエージェント側の依存が解決済みでない環境（テスト等）でも
FastAPI 起動時にエラーにならないように。
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


def _sse_event(event: str, data: dict | None = None) -> str:
    """SSE フレームを生成する。"""
    payload = json.dumps(data or {}, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _build_graph():
    """Lazily import and build the commission graph."""
    from app.commission_engine.graph import build_commission_graph

    return build_commission_graph()


async def run_calculate(
    *,
    session_id: str,
    uploaded_files: list[dict],
    threshold: int = 100_000,
) -> AsyncIterator[tuple[str, dict]]:
    """グラフを start から hitl_review/END まで回し、(event, data) を yield する。

    呼び出し側はこのイテレータを SSE 形式に変換して返す。
    """
    yield "status", {"node": "supervisor", "message": "計算ワークフロー開始"}

    try:
        graph = _build_graph()
    except Exception as e:
        logger.exception("graph build failed")
        yield "error", {"message": f"グラフ初期化失敗: {e}"}
        return

    config = {"configurable": {"thread_id": session_id}}
    initial_state = {
        "uploaded_files": uploaded_files,
        "processing_status": "parsing",
        # supervisor が data_parser へルーティングするように指示
        "next_route": "data_parser",
    }

    try:
        async for chunk in graph.astream(
            initial_state, config=config, stream_mode="updates"
        ):
            for node_name, node_output in chunk.items():
                # interrupt が発生したノードは特殊フィールドが入る
                if isinstance(node_output, dict) and node_output.get("__interrupt__"):
                    intr = node_output["__interrupt__"]
                    yield "hitl_required", {
                        "node": node_name,
                        "payload": _extract_interrupt_value(intr),
                    }
                    return

                yield "progress", {
                    "node": node_name,
                    "status": "completed",
                    "message": _summarize_node_output(node_name, node_output),
                }

        # ストリーム終了後の最終 state スナップショット
        snap = await graph.aget_state(config)
        if snap.next and "hitl_review" in snap.next:
            # 念のため interrupt 検出
            yield "hitl_required", {"node": "hitl_review", "payload": {}}
            return

        yield "result", _final_result_from_state(snap.values)
        yield "done", {}
    except Exception as e:
        logger.exception("graph stream failed")
        yield "error", {"message": str(e)}


async def resume_with_decisions(
    *,
    session_id: str,
    decisions: list[dict],
) -> AsyncIterator[tuple[str, dict]]:
    """HITL 中断中のグラフを Command(resume=decisions) で再開する。"""
    from langgraph.types import Command

    graph = _build_graph()
    config = {"configurable": {"thread_id": session_id}}

    try:
        async for chunk in graph.astream(
            Command(resume=decisions), config=config, stream_mode="updates"
        ):
            for node_name, node_output in chunk.items():
                yield "progress", {
                    "node": node_name,
                    "status": "completed",
                    "message": _summarize_node_output(node_name, node_output),
                }

        snap = await graph.aget_state(config)
        yield "result", _final_result_from_state(snap.values)
        yield "done", {}
    except Exception as e:
        logger.exception("graph resume failed")
        yield "error", {"message": str(e)}


def _extract_interrupt_value(intr: Any) -> dict:
    """LangGraph の interrupt payload を取り出す。"""
    if isinstance(intr, list) and intr:
        first = intr[0]
        if hasattr(first, "value"):
            return first.value if isinstance(first.value, dict) else {"value": first.value}
        if isinstance(first, dict):
            return first
    if isinstance(intr, dict):
        return intr
    return {"value": str(intr)}


def _summarize_node_output(node_name: str, output: Any) -> str:
    """ノード出力を 1 行サマリ化（SSE 表示用）。"""
    if not isinstance(output, dict):
        return f"{node_name} 完了"
    if node_name == "data_parser":
        sales = len(output.get("sales_records") or [])
        master = len(output.get("master_records") or {})
        return f"パース完了: 売上明細 {sales} 行 / マスタ {master} 件"
    if node_name == "calculator":
        s = output.get("summary") or {}
        return (
            f"計算完了: 自動完了 {s.get('auto_completed', 0)} 件 / "
            f"HITL対象 {s.get('hitl_pending', 0)} 件 / "
            f"合計 {s.get('total_commission_amount', 0):,} 円"
        )
    if node_name == "approve":
        approved = output.get("approved_results") or []
        return f"承認確定: {len(approved)} 件"
    return f"{node_name} 完了"


def _final_result_from_state(values: dict) -> dict:
    """最終 state から SSE 'result' イベントのペイロードを抽出。"""
    return {
        "summary": values.get("summary", {}),
        "pending_hitl_count": len(values.get("pending_hitl") or []),
        "approved_count": len(values.get("approved_results") or []),
        "processing_status": values.get("processing_status", "idle"),
    }


async def stream_to_sse(
    iterator: AsyncIterator[tuple[str, dict]],
) -> AsyncIterator[str]:
    """(event, data) のイテレータを SSE 文字列に変換。"""
    async for ev, data in iterator:
        yield _sse_event(ev, data)
