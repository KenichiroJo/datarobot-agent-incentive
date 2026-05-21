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
"""販売管理手数料計算 API ルーター。

6 エンドポイント:
- POST   /api/v1/commission/upload           : Excel multipart upload
- POST   /api/v1/commission/calculate        : SSE で進捗 stream
- GET    /api/v1/commission/results/{sid}    : ページネーション付き結果取得
- POST   /api/v1/commission/hitl/approve     : HITL 承認 → graph resume
- GET    /api/v1/commission/export/{sid}     : CSV ダウンロード
- GET    /api/v1/commission/dashboard/{sid}  : ダッシュボード集計
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
from decimal import Decimal
from typing import Any, AsyncIterator

from datarobot.auth.session import AuthCtx
from datarobot.auth.typing import Metadata
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessageChunk

from app.api.v1.commission_schema import (
    CalculateRequest,
    DashboardEventItem,
    DashboardKpi,
    DashboardResponse,
    HITLApproveRequest,
    HITLApproveResponse,
    PartnerAggregate,
    ProductAggregate,
    ResultRecord,
    ResultsResponse,
    UploadedFileInfo,
    UploadResponse,
)
from app.auth.ctx import must_get_auth_ctx
from app.services.commission_runner import sse_frame
from app.services.commission_session_store import CommissionSessionStore

logger = logging.getLogger(__name__)

commission_router = APIRouter(prefix="/commission", tags=["Commission"])


# ===============================================================
# Helpers
# ===============================================================


def _get_store(request: Request) -> CommissionSessionStore:
    """app.state.deps から CommissionSessionStore を取り出す。"""
    deps = request.app.state.deps
    store: CommissionSessionStore | None = getattr(deps, "commission_store", None)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="commission_store が初期化されていません",
        )
    return store


def _decimal_to_int(value: Any) -> int:
    if isinstance(value, Decimal):
        return int(value.to_integral_value())
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def _result_to_schema(r: dict[str, Any]) -> ResultRecord:
    """calculator の dict 出力を ResultRecord に変換。Decimal は int に丸める。"""
    return ResultRecord(
        record_no=r.get("record_no"),
        partner_code=r.get("取引先コード"),
        partner_name=r.get("取引先名称"),
        product=r.get("商材"),
        payment_method=r.get("決済方法"),
        total_commission=_decimal_to_int(r.get("total_commission")),
        basic_commission=_decimal_to_int(r.get("basic_commission")),
        volume_incentive=_decimal_to_int(r.get("volume_incentive")),
        special_commission_1=_decimal_to_int(r.get("special_commission_1")),
        special_commission_2=_decimal_to_int(r.get("special_commission_2")),
        continuous_commission=_decimal_to_int(r.get("continuous_commission")),
        referral_commission=_decimal_to_int(r.get("referral_commission")),
        pap_commission=_decimal_to_int(r.get("pap_commission")),
        pas_commission=_decimal_to_int(r.get("pas_commission")),
        ph_commission=_decimal_to_int(r.get("ph_commission")),
        qi_amount=_decimal_to_int(r.get("qi_amount")),
        debit_initial_fee=_decimal_to_int(r.get("debit_initial_fee")),
        return_amount=_decimal_to_int(r.get("return_amount")),
        master_found=bool(r.get("master_found")),
        is_anomaly=bool(r.get("is_anomaly")),
        status=str(r.get("status", "unknown")),
        hitl_reason=r.get("hitl_reason"),
        hitl_reason_ja=r.get("hitl_reason_ja"),
        master_key_used=r.get("master_key_used"),
        calculation_trace=r.get("calculation_trace", []) or [],
    )


# ===============================================================
# 1. POST /upload — multipart ファイル受付
# ===============================================================


@commission_router.post("/upload", response_model=UploadResponse)
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(...),
    session_id: str | None = Form(default=None),
    auth_ctx: AuthCtx[Metadata] = Depends(must_get_auth_ctx),
) -> UploadResponse:
    """売上明細 / 取引条件マスタ Excel をアップロードする。

    ファイル名から種別を自動判定 (売上 / マスタ / unknown)。
    """
    store = _get_store(request)
    sess = store.get_or_create(session_id, user_id=str(auth_ctx.user.id))

    config = request.app.state.deps.config
    max_bytes = getattr(config, "commission_max_upload_mb", 50) * 1024 * 1024

    uploaded: list[UploadedFileInfo] = []
    for f in files:
        try:
            stored = store.file_storage.save(
                session_id=sess.session_id,
                original_filename=f.filename or "upload.xlsx",
                source=f.file,
                max_bytes=max_bytes,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        sess.file_paths[stored.file_id] = stored
        sess.push_event(
            "upload",
            f"{stored.filename} を保存 ({stored.size:,} bytes, 種別={stored.detected_type})",
            {"file_id": stored.file_id, "detected_type": stored.detected_type},
        )

        uploaded.append(
            UploadedFileInfo(
                file_id=stored.file_id,
                filename=stored.filename,
                size=stored.size,
                detected_type=stored.detected_type,  # type: ignore[arg-type]
            )
        )

    return UploadResponse(
        session_id=sess.session_id,
        uploaded=uploaded,
        message=f"{len(uploaded)} 件のファイルをアップロードしました。",
    )


# ===============================================================
# 2. POST /calculate — SSE で進捗 stream
# ===============================================================


@commission_router.post("/calculate")
async def calculate(
    request: Request,
    body: CalculateRequest,
    auth_ctx: AuthCtx[Metadata] = Depends(must_get_auth_ctx),  # noqa: ARG001
) -> StreamingResponse:
    """LangGraph グラフを起動し、進捗を SSE でストリーミング配信する。

    interrupt_before=['hitl_review'] によりレビュー対象がある場合は graph が
    その手前で停止する。クライアントは ``{type:'done', reason:'hitl_required'}`` を
    受け取って ReviewPage に遷移する。
    """
    store = _get_store(request)
    try:
        sess = store.must_get(body.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    threshold = body.options.anomaly_threshold
    file_ids = body.file_ids or list(sess.file_paths.keys())
    uploaded_files = [
        {
            "file_id": sess.file_paths[fid].file_id,
            "filename": sess.file_paths[fid].filename,
            "detected_type": sess.file_paths[fid].detected_type,
            "path": str(sess.file_paths[fid].path),
        }
        for fid in file_ids
        if fid in sess.file_paths
    ]
    if not uploaded_files:
        raise HTTPException(status_code=400, detail="アップロード済みファイルがありません")

    sess.push_event("calculate_start", "計算ジョブを開始")

    async def event_stream() -> AsyncIterator[str]:
        """LangGraph の astream を SSE フレームに変換する。"""
        compiled = store.compiled_graph
        config = {
            "configurable": {"thread_id": sess.session_id},
            "recursion_limit": 150,
        }
        # 並列 stream を防ぐ
        async with sess.lock:
            try:
                yield sse_frame({"type": "status", "message": "ファイルをパースしています..."})

                initial_input = {
                    "messages": [HumanMessage(content="ファイルをパースして手数料を計算してください。")],
                    "uploaded_files": uploaded_files,
                    "anomaly_threshold": threshold,
                    "processing_status": "parsing",
                }

                async for stream_mode, payload in compiled.astream(
                    initial_input,
                    config=config,
                    stream_mode=["updates", "messages", "values"],
                ):
                    async for frame in _translate_stream_event(stream_mode, payload, sess):
                        yield frame

                # 最終 state を確認: interrupt されていれば HITL 待ち、そうでなければ完了
                snap = compiled.get_state(config)
                vals = snap.values if snap else {}
                if vals.get("processing_status") == "awaiting_hitl":
                    pending = vals.get("pending_hitl", [])
                    summary = vals.get("summary", {})
                    yield sse_frame(
                        {
                            "type": "result",
                            "data": {
                                "summary": summary,
                                "anomaly_count": len(pending),
                                "hitl_required": True,
                            },
                        }
                    )
                    yield sse_frame({"type": "done", "reason": "hitl_required"})
                else:
                    yield sse_frame(
                        {
                            "type": "result",
                            "data": {
                                "summary": vals.get("summary", {}),
                                "anomaly_count": 0,
                                "hitl_required": False,
                            },
                        }
                    )
                    yield sse_frame({"type": "done", "reason": "completed"})

            except asyncio.CancelledError:
                logger.info("calculate stream cancelled by client session=%s", sess.session_id)
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("calculate stream failed session=%s", sess.session_id)
                yield sse_frame({"type": "error", "message": str(exc)})
                yield sse_frame({"type": "done", "reason": "error"})

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


async def _translate_stream_event(
    stream_mode: str, payload: Any, sess: Any
) -> AsyncIterator[str]:
    """LangGraph のイベントを SSE フレームに変換する。"""
    if stream_mode == "updates":
        # payload は {node_name: state_delta}
        if isinstance(payload, dict):
            for node_name, delta in payload.items():
                ps = delta.get("processing_status") if isinstance(delta, dict) else None
                msg_text = ""
                if isinstance(delta, dict) and delta.get("messages"):
                    last_msg = delta["messages"][-1]
                    msg_text = getattr(last_msg, "content", "") or ""
                yield sse_frame(
                    {
                        "type": "status",
                        "node": node_name,
                        "status": ps,
                        "message": str(msg_text),
                    }
                )
                # calculator ノード完了時に進捗を発火
                if node_name == "calculator" and isinstance(delta, dict):
                    calc_results = delta.get("calculation_results") or []
                    yield sse_frame(
                        {
                            "type": "progress",
                            "current": len(calc_results),
                            "total": len(calc_results),
                        }
                    )
                    sess.push_event(
                        "calculate_done",
                        f"{len(calc_results)} 件を計算しました",
                    )

    elif stream_mode == "messages":
        # explainer ノードからのトークンを result delta として流す
        try:
            chunk, meta = payload
        except (TypeError, ValueError):
            return
        if isinstance(chunk, AIMessageChunk) and meta.get("langgraph_node") == "explainer":
            content = str(chunk.content)
            if content:
                yield sse_frame({"type": "result", "delta": content})

    elif stream_mode == "values":
        # values は最新 state snapshot。interrupt 検出に使う
        if isinstance(payload, dict) and payload.get("processing_status") == "awaiting_hitl":
            # interrupt 通知は呼び出し元 (event_stream 末尾) で done を送るので
            # ここでは status だけ送る
            yield sse_frame(
                {
                    "type": "status",
                    "status": "awaiting_hitl",
                    "message": "HITL 承認待ちのレコードがあります",
                    "pending_count": len(payload.get("pending_hitl", []) or []),
                }
            )


# ===============================================================
# 3. GET /results/{session_id}
# ===============================================================


@commission_router.get("/results/{session_id}", response_model=ResultsResponse)
async def get_results(
    request: Request,
    session_id: str,
    status_filter: str | None = Query(default="all", alias="status"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=500),
    auth_ctx: AuthCtx[Metadata] = Depends(must_get_auth_ctx),  # noqa: ARG001
) -> ResultsResponse:
    store = _get_store(request)
    try:
        store.must_get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    state = store.get_state(session_id)
    results: list[dict[str, Any]] = state.get("calculation_results", []) or []
    approved = state.get("approved_results", []) or []
    pending = state.get("pending_hitl", []) or []

    if status_filter == "hitl_pending":
        rows = pending
    elif status_filter == "approved":
        rows = approved
    elif status_filter == "error":
        rows = [r for r in results if r.get("status") == "calc_error"]
    else:
        rows = results

    total = len(rows)
    start = (page - 1) * per_page
    sliced = rows[start : start + per_page]

    return ResultsResponse(
        session_id=session_id,
        records=[_result_to_schema(r) for r in sliced],
        total=total,
        page=page,
        per_page=per_page,
        summary=state.get("summary"),
    )


# ===============================================================
# 4. POST /hitl/approve
# ===============================================================


@commission_router.post("/hitl/approve", response_model=HITLApproveResponse)
async def hitl_approve(
    request: Request,
    body: HITLApproveRequest,
    auth_ctx: AuthCtx[Metadata] = Depends(must_get_auth_ctx),  # noqa: ARG001
) -> HITLApproveResponse:
    """HITL 承認結果を反映して graph を resume する。

    1. pending_hitl の各レコードに hitl_decided / hitl_action / manual_amount をマージ
    2. compiled_graph.aupdate_state で state を更新
    3. compiled_graph.astream(None) で graph を resume
    """
    store = _get_store(request)
    try:
        sess = store.must_get(body.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    state = store.get_state(body.session_id)
    pending: list[dict[str, Any]] = list(state.get("pending_hitl", []) or [])

    decisions = {a.record_no: a for a in body.approvals}
    approved_count = 0
    rejected_count = 0
    manual_count = 0

    new_pending: list[dict[str, Any]] = []
    for p in pending:
        rno = p.get("record_no")
        if rno in decisions:
            d = decisions[rno]
            new_pending.append(
                {
                    **p,
                    "hitl_decided": True,
                    "hitl_action": d.action,
                    "manual_amount": d.manual_amount,
                }
            )
            if d.action == "approve":
                approved_count += 1
            elif d.action == "reject":
                rejected_count += 1
            elif d.action == "manual":
                manual_count += 1
        else:
            new_pending.append(p)

    remaining = sum(1 for p in new_pending if not p.get("hitl_decided"))

    # State 更新 → resume
    await store.update_state(body.session_id, {"pending_hitl": new_pending})

    sess.push_event(
        "hitl_decisions",
        f"{approved_count + manual_count} 件承認 / {rejected_count} 件却下",
    )

    # 残り 0 件なら approve ノードを進める。残っている場合は state 更新のみ。
    if remaining == 0:
        # interrupt 後の resume: astream(None, config) で実行継続
        config = {
            "configurable": {"thread_id": body.session_id},
            "recursion_limit": 150,
        }
        async with sess.lock:
            try:
                async for _ in store.compiled_graph.astream(
                    None, config=config, stream_mode=["updates"]
                ):
                    pass  # resume を完走させるだけ
            except Exception:  # noqa: BLE001
                logger.exception("HITL resume failed session=%s", body.session_id)
                raise HTTPException(status_code=500, detail="HITL 後の処理に失敗")

    return HITLApproveResponse(
        approved_count=approved_count,
        rejected_count=rejected_count,
        manual_count=manual_count,
        remaining_hitl=remaining,
    )


# ===============================================================
# 5. GET /export/{session_id}
# ===============================================================


@commission_router.get("/export/{session_id}")
async def export_csv(
    request: Request,
    session_id: str,
    auth_ctx: AuthCtx[Metadata] = Depends(must_get_auth_ctx),  # noqa: ARG001
) -> StreamingResponse:
    """確定済みコミッションを CSV でダウンロード。"""
    store = _get_store(request)
    try:
        store.must_get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    state = store.get_state(session_id)
    approved: list[dict[str, Any]] = state.get("approved_results", []) or []
    if not approved:
        # 確定済みが無い場合は calculation_results の master_found のみを出力
        approved = [
            r for r in (state.get("calculation_results", []) or []) if r.get("master_found")
        ]

    buf = io.StringIO()
    # spec の列順
    header = [
        "レコードNo",
        "取引先コード",
        "取引先名称",
        "商材",
        "決済方法",
        "基本コミッション",
        "ボリュームインセンティブ",
        "特別コミッション①",
        "特別コミッション②",
        "継続コミッション",
        "紹介制度コミッション",
        "PAPコミッション",
        "PASコミッション",
        "PHコミッション",
        "QI分割額",
        "口振初回手数料",
        "戻入手数料",
        "合計手数料",
        "ステータス",
        "計算根拠",
    ]
    writer = csv.writer(buf)
    writer.writerow(header)
    for r in approved:
        writer.writerow(
            [
                r.get("record_no"),
                r.get("取引先コード"),
                r.get("取引先名称"),
                r.get("商材"),
                r.get("決済方法"),
                _decimal_to_int(r.get("basic_commission")),
                _decimal_to_int(r.get("volume_incentive")),
                _decimal_to_int(r.get("special_commission_1")),
                _decimal_to_int(r.get("special_commission_2")),
                _decimal_to_int(r.get("continuous_commission")),
                _decimal_to_int(r.get("referral_commission")),
                _decimal_to_int(r.get("pap_commission")),
                _decimal_to_int(r.get("pas_commission")),
                _decimal_to_int(r.get("ph_commission")),
                _decimal_to_int(r.get("qi_amount")),
                _decimal_to_int(r.get("debit_initial_fee")),
                _decimal_to_int(r.get("return_amount")),
                _decimal_to_int(r.get("total_commission")),
                r.get("status"),
                " / ".join(r.get("calculation_trace", []) or []),
            ]
        )

    buf.seek(0)
    headers = {
        "Content-Disposition": f'attachment; filename="commission_{session_id}.csv"',
    }
    # Excel で開けるよう BOM 付き UTF-8 で配信
    csv_bytes = ("﻿" + buf.getvalue()).encode("utf-8")
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


# ===============================================================
# 6. GET /dashboard/{session_id}
# ===============================================================


@commission_router.get("/dashboard/{session_id}", response_model=DashboardResponse)
async def dashboard(
    request: Request,
    session_id: str,
    auth_ctx: AuthCtx[Metadata] = Depends(must_get_auth_ctx),  # noqa: ARG001
) -> DashboardResponse:
    store = _get_store(request)
    try:
        sess = store.must_get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    state = store.get_state(session_id)
    summary = state.get("summary", {}) or {}
    kpi_raw = summary.get("kpi", {}) or {}
    by_partner = summary.get("by_partner", []) or []
    by_product = summary.get("by_product", []) or []
    by_status = summary.get("by_status", {}) or {}

    phases = {
        "upload": "completed" if sess.file_paths else "pending",
        "parse": "completed" if state.get("sales_records") else "pending",
        "calculate": "completed" if state.get("calculation_results") else "pending",
        "review": "in_progress"
        if state.get("processing_status") == "awaiting_hitl"
        else ("completed" if state.get("approved_results") else "pending"),
        "finalize": "completed" if state.get("approved_results") else "pending",
    }

    return DashboardResponse(
        session_id=session_id,
        kpi=DashboardKpi(
            total_records=kpi_raw.get("total_records", 0),
            auto_completed=kpi_raw.get("auto_completed", 0),
            hitl_pending=kpi_raw.get("hitl_pending", 0),
            hitl_approved=kpi_raw.get("hitl_approved", 0),
            error_count=kpi_raw.get("error_count", 0),
            total_commission_amount=kpi_raw.get("total_commission_amount", 0),
            auto_completion_rate=kpi_raw.get("auto_completion_rate", 0.0),
        ),
        by_partner=[
            PartnerAggregate(**p) for p in by_partner if isinstance(p, dict)
        ],
        by_product=[
            ProductAggregate(**p) for p in by_product if isinstance(p, dict)
        ],
        by_status=by_status,
        processing_phases=phases,
        events=[DashboardEventItem(**e) for e in sess.events[-10:]],
    )


# ===============================================================
# Convenience: session reset
# ===============================================================


@commission_router.post("/session/reset")
async def reset_session(
    request: Request,
    session_id: str = Form(...),
    auth_ctx: AuthCtx[Metadata] = Depends(must_get_auth_ctx),  # noqa: ARG001
) -> dict[str, str]:
    store = _get_store(request)
    store.reset(session_id)
    return {"status": "reset", "session_id": session_id}
