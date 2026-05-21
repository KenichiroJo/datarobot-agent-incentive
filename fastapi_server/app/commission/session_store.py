"""手数料計算セッションをインメモリで管理するストア。

PoC 用なのでプロセス再起動でセッションが消失する。本番化時は sqlmodel テーブルへ移行。
LangGraph 自体のチェックポイントは agent.commission.graph._memory が別途保持する。
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class UploadedFile:
    file_id: str
    filename: str
    path: str
    size: int
    detected_type: str


@dataclass
class CommissionSession:
    session_id: str
    uploaded_files: list[UploadedFile] = field(default_factory=list)
    state_snapshot: dict[str, Any] = field(default_factory=dict)
    processing_status: str = "idle"
    # 計算済みの結果（state_snapshot["calculation_results"] と同期）
    calculation_results: list[dict] = field(default_factory=list)
    pending_hitl: list[dict] = field(default_factory=list)
    approved_results: list[dict] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    last_error: str | None = None

    def to_state(self) -> dict[str, Any]:
        """LangGraph の initial state に変換する。"""
        return {
            "uploaded_files": [
                {
                    "file_id": f.file_id,
                    "filename": f.filename,
                    "path": f.path,
                    "detected_type": f.detected_type,
                }
                for f in self.uploaded_files
            ],
            "processing_status": "parsing",
        }


class CommissionSessionStore:
    """セッション ID をキーとしたインメモリストア。"""

    def __init__(self, upload_root: Path | None = None) -> None:
        self._sessions: dict[str, CommissionSession] = {}
        self._lock = asyncio.Lock()
        self.upload_root = upload_root or Path("/tmp/commission_uploads")
        self.upload_root.mkdir(parents=True, exist_ok=True)

    async def create(self) -> CommissionSession:
        async with self._lock:
            sid = uuid4().hex
            s = CommissionSession(session_id=sid)
            self._sessions[sid] = s
            (self.upload_root / sid).mkdir(parents=True, exist_ok=True)
            return s

    async def get(self, session_id: str) -> CommissionSession | None:
        return self._sessions.get(session_id)

    async def add_file(
        self,
        session_id: str,
        filename: str,
        content: bytes,
        detected_type: str,
    ) -> UploadedFile:
        sess = await self.get(session_id)
        if sess is None:
            raise KeyError(session_id)
        file_id = uuid4().hex
        # 安全のためファイル名はオリジナルを保持しつつ uuid プレフィックスで衝突回避
        safe_name = f"{file_id}_{filename}"
        target = self.upload_root / session_id / safe_name
        target.write_bytes(content)
        f = UploadedFile(
            file_id=file_id,
            filename=filename,
            path=str(target),
            size=len(content),
            detected_type=detected_type,
        )
        sess.uploaded_files.append(f)
        return f

    async def update_results(
        self,
        session_id: str,
        *,
        calculation_results: list[dict] | None = None,
        pending_hitl: list[dict] | None = None,
        approved_results: list[dict] | None = None,
        summary: dict | None = None,
        processing_status: str | None = None,
        error: str | None = None,
    ) -> None:
        sess = await self.get(session_id)
        if sess is None:
            return
        if calculation_results is not None:
            sess.calculation_results = calculation_results
        if pending_hitl is not None:
            sess.pending_hitl = pending_hitl
        if approved_results is not None:
            sess.approved_results = approved_results
        if summary is not None:
            sess.summary = summary
        if processing_status is not None:
            sess.processing_status = processing_status
        if error is not None:
            sess.last_error = error

    async def cleanup(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)
            target = self.upload_root / session_id
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
