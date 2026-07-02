"""手数料計算パイプラインを SSE イベント列に変換するドライバ。

大容量ファイル対策として、パース・計算といった重い同期処理は
``run_in_executor`` で別スレッドに逃がし、イベントループを塞がずに
SSE 進捗をリアルタイム配信する。進捗は thread-safe な asyncio.Queue で受け渡す。

LangGraph の interrupt/checkpointer は使わず、計算結果はセッションストアに
直接書き込む（ハング要因の排除・デバッグ容易化のため）。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Callable

from app.commission_engine.anomaly_detector import detect_anomalies
from app.commission_engine.commission_calculator import calculate_commission
from app.commission_engine.excel_parser import parse_master_excel, parse_sales_excel
from app.commission_engine.report_generator import generate_summary

logger = logging.getLogger(__name__)

# この行数を超えたら、確定済み（異常なし）レコードの計算トレースを
# 末尾 1 行に圧縮してメモリを節約する（HITL 対象は全トレース保持）。
_TRACE_TRIM_THRESHOLD = 20_000

_CALC_PROGRESS_EVERY = 2000

# 無通信がこの秒数続いたら keepalive を送る。プロキシ (proxy_read_timeout
# 既定 60s) のアイドルタイムアウトによる SSE 切断を防ぐため。
_HEARTBEAT_SEC = 15.0
# SSE コメント行。フロントの自前パーサでは event:/data: に一致しないため無害に無視される。
_HEARTBEAT_FRAME = ": ping\n\n"


def _sse_event(event: str, data: dict | None = None) -> str:
    """SSE フレームを生成する。"""
    payload = json.dumps(data or {}, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


async def _run_blocking_with_progress(
    fn: Callable[..., Any], *args: Any
) -> AsyncIterator[tuple[str, Any, Any]]:
    """ブロッキング関数 fn を別スレッドで実行しつつ進捗をストリームする。

    fn は progress_cb(done, total) を受け取れること。
    yield するタプル:
      ("progress", done, total)
      ("result", value, None)  — 完了
      ("error", exception, None) — 例外
    """
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def progress_cb(done: int, total: int | None = None) -> None:
        loop.call_soon_threadsafe(q.put_nowait, ("progress", done, total))

    def worker() -> None:
        try:
            res = fn(*args, progress_cb=progress_cb)
            loop.call_soon_threadsafe(q.put_nowait, ("result", res, None))
        except Exception as e:  # noqa: BLE001
            loop.call_soon_threadsafe(q.put_nowait, ("error", e, None))

    loop.run_in_executor(None, worker)

    while True:
        kind, a, b = await q.get()
        yield kind, a, b
        if kind in ("result", "error"):
            return


def _calculate_all(
    sales: list[dict], master: dict[str, dict], progress_cb: Callable | None = None
) -> list[dict]:
    """全売上明細に手数料計算を適用する（別スレッドで実行される）。"""
    results: list[dict] = []
    total = len(sales)
    for i, rec in enumerate(sales, 1):
        results.append(calculate_commission(rec, master))
        if progress_cb and i % _CALC_PROGRESS_EVERY == 0:
            progress_cb(i, total)
    if progress_cb:
        progress_cb(total, total)
    return results


def _split_files(uploaded_files: list[dict]) -> tuple[list[dict], list[dict]]:
    """アップロードファイルを売上明細 / マスタに振り分ける。"""

    def detect(f: dict) -> str:
        t = f.get("detected_type")
        if t in ("sales", "master"):
            return t
        name = f.get("filename", "")
        if "売上明細" in name or "売上" in name:
            return "sales"
        if "取引条件" in name or "マスタ" in name:
            return "master"
        return "unknown"

    sales = [f for f in uploaded_files if detect(f) == "sales"]
    master = [f for f in uploaded_files if detect(f) == "master"]
    return sales, master


async def run_calculate(
    *,
    store: Any,
    session_id: str,
    uploaded_files: list[dict],
    threshold: int = 100_000,
) -> AsyncIterator[tuple[str, dict]]:
    """パース → 計算 → 異常検知 → 集計 を実行し (event, data) を yield する。

    重い処理は別スレッドで実行され、進捗が随時 SSE として流れる。
    結果はセッションストアに直接書き込む。
    """
    yield "status", {"message": "計算ワークフロー開始"}

    sales_files, master_files = _split_files(uploaded_files)
    if not sales_files:
        yield "error", {"message": "売上明細ファイルが見つかりません"}
        return

    try:
        # --- マスタ読み込み ---
        master: dict[str, dict] = {}
        for mf in master_files:
            yield "progress", {"message": f"取引条件マスタ読み込み中: {mf['filename']}"}
            async for kind, a, _b in _run_blocking_with_progress(
                parse_master_excel, mf["path"]
            ):
                if kind == "progress":
                    yield "progress", {"message": f"マスタ {a:,} 行 読み込み中…"}
                elif kind == "result":
                    master.update(a)
                elif kind == "error":
                    raise a
        yield "progress", {"message": f"マスタ {len(master):,} 件 読み込み完了"}

        # --- 売上明細読み込み ---
        sales: list[dict] = []
        for sf in sales_files:
            yield "progress", {"message": f"売上明細読み込み中: {sf['filename']}"}
            async for kind, a, _b in _run_blocking_with_progress(
                parse_sales_excel, sf["path"]
            ):
                if kind == "progress":
                    yield "progress", {"message": f"売上明細 {a:,} 行 読み込み中…"}
                elif kind == "result":
                    sales.extend(a)
                elif kind == "error":
                    raise a
        yield "progress", {"message": f"売上明細 {len(sales):,} 行 読み込み完了"}

        if not sales:
            yield "error", {"message": "売上明細データが読み込めませんでした"}
            return

        # --- 手数料計算 ---
        yield "progress", {"message": "手数料計算中…"}
        results: list[dict] = []
        async for kind, a, b in _run_blocking_with_progress(
            _calculate_all, sales, master
        ):
            if kind == "progress":
                total = b or len(sales)
                yield "progress", {"message": f"手数料計算中… {a:,}/{total:,} 件"}
            elif kind == "result":
                results = a
            elif kind == "error":
                raise a

        # --- 異常検知・集計（大量行の可能性があるためスレッドへ）---
        pending = await asyncio.to_thread(detect_anomalies, results, threshold)
        summary = await asyncio.to_thread(generate_summary, results)

        # 大容量時はトレースを圧縮してメモリ節約（HITL 対象は全保持）
        if len(results) > _TRACE_TRIM_THRESHOLD:
            for r in results:
                if not r.get("is_anomaly") and r.get("calculation_trace"):
                    r["calculation_trace"] = r["calculation_trace"][-1:]

        approved = [] if pending else list(results)
        await store.update_results(
            session_id,
            calculation_results=results,
            pending_hitl=pending,
            approved_results=approved,
            summary=summary,
            processing_status="review" if pending else "approved",
        )

        yield "progress", {
            "message": (
                f"計算完了: 自動完了 {summary['auto_completed']:,} 件 / "
                f"HITL対象 {summary['hitl_pending']:,} 件 / "
                f"合計 {summary['total_commission_amount']:,} 円"
            )
        }

        if pending:
            yield "hitl_required", {"payload": {"pending_count": len(pending)}}
        else:
            yield "result", {
                "summary": summary,
                "pending_hitl_count": 0,
                "approved_count": len(results),
            }
            yield "done", {}
    except Exception as e:  # noqa: BLE001
        logger.exception("run_calculate failed")
        try:
            await store.update_results(
                session_id, processing_status="error", error=str(e)
            )
        except Exception:  # noqa: BLE001
            pass
        yield "error", {"message": str(e)}


async def stream_to_sse(
    iterator: AsyncIterator[tuple[str, dict]],
) -> AsyncIterator[str]:
    """(event, data) のイテレータを SSE 文字列に変換し、keepalive を挿入する。

    重いパース/計算の最中でソースが長時間 yield しなくても、_HEARTBEAT_SEC ごとに
    SSE コメント行を送出してプロキシのアイドルタイムアウトによる切断を防ぐ。

    実装: ソースを背景タスクでキューに流し込み、本ループはタイムアウト付きで
    キューから取り出す。タイムアウト時のみ keepalive を送る（イベントは取りこぼさない）。
    """
    queue: asyncio.Queue = asyncio.Queue()
    done = object()

    async def _pump() -> None:
        try:
            async for item in iterator:
                await queue.put(item)
        except Exception as e:  # noqa: BLE001
            logger.exception("sse source failed")
            await queue.put(("error", {"message": str(e)}))
        finally:
            await queue.put(done)

    task = asyncio.ensure_future(_pump())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), _HEARTBEAT_SEC)
            except asyncio.TimeoutError:
                yield _HEARTBEAT_FRAME
                continue
            if item is done:
                return
            ev, data = item
            yield _sse_event(ev, data)
    finally:
        task.cancel()
