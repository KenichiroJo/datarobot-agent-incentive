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
"""コミッション計算のセッション管理 (インメモリ)。

設計判断:
- 単一プロセス内に 1 個のコンパイル済みグラフを保持し、``thread_id == session_id`` で
  multi-tenant 分離する (LangGraph 標準パターン)
- 各セッションは asyncio.Lock を持ち、同一 session への並列 stream を防止
- TTL ベースの簡易 eviction (Lazy: get_or_create 呼ばれた時に古いものを削除)
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.file_storage import CommissionFileStorage, StoredFile

logger = logging.getLogger(__name__)


@dataclass
class CommissionSession:
    """1 セッションあたりの状態。"""

    session_id: str
    user_id: str
    created_at: float = field(default_factory=time.time)
    last_event_at: float = field(default_factory=time.time)
    file_paths: dict[str, StoredFile] = field(default_factory=dict)
    # 同一 session への並列 stream 防止用
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # ダッシュボード用イベントログ (最新 N 件)
    events: list[dict[str, Any]] = field(default_factory=list)

    MAX_EVENTS = 50

    def touch(self) -> None:
        self.last_event_at = time.time()

    def push_event(self, kind: str, message: str, meta: dict[str, Any] | None = None) -> None:
        """ダッシュボード timeline 用のイベント追加。"""
        self.events.append(
            {
                "id": uuid.uuid4().hex[:8],
                "kind": kind,
                "message": message,
                "meta": meta or {},
                "ts": time.time(),
            }
        )
        if len(self.events) > self.MAX_EVENTS:
            del self.events[: len(self.events) - self.MAX_EVENTS]


class CommissionSessionStore:
    """process-wide のセッション管理。

    シングルトンとして app.state.deps から参照される。
    """

    def __init__(
        self,
        file_storage: CommissionFileStorage,
        ttl_seconds: int = 7 * 24 * 60 * 60,
    ) -> None:
        self._sessions: dict[str, CommissionSession] = {}
        self._compiled: Any | None = None
        self._compiled_lock = threading.Lock()
        self._ttl = ttl_seconds
        self._file_storage = file_storage

    @property
    def file_storage(self) -> CommissionFileStorage:
        return self._file_storage

    # --------- compiled graph (lazy init) ---------

    @property
    def compiled_graph(self) -> Any:
        """コンパイル済みグラフを返す (lazy 初期化)。LLM 接続を遅延化するため。"""
        if self._compiled is not None:
            return self._compiled
        with self._compiled_lock:
            if self._compiled is not None:
                return self._compiled
            from app.services.commission_runner import build_compiled_commission_graph

            self._compiled = build_compiled_commission_graph()
        return self._compiled

    # --------- session lifecycle ---------

    def get_or_create(
        self, session_id: str | None, user_id: str
    ) -> CommissionSession:
        """セッションを取得 or 生成する。session_id が None の場合は新規発行。"""
        self._evict_expired()
        if session_id and session_id in self._sessions:
            sess = self._sessions[session_id]
            sess.touch()
            return sess
        sid = session_id or uuid.uuid4().hex
        sess = CommissionSession(session_id=sid, user_id=user_id)
        self._sessions[sid] = sess
        sess.push_event("session_created", f"セッション {sid} を開始しました")
        logger.info("session created session_id=%s user=%s", sid, user_id)
        return sess

    def get(self, session_id: str) -> CommissionSession | None:
        sess = self._sessions.get(session_id)
        if sess:
            sess.touch()
        return sess

    def must_get(self, session_id: str) -> CommissionSession:
        sess = self.get(session_id)
        if sess is None:
            raise KeyError(f"セッションが見つかりません: {session_id}")
        return sess

    def reset(self, session_id: str) -> None:
        """セッションとファイルを削除する (UI のリセットボタン用)。"""
        sess = self._sessions.pop(session_id, None)
        if sess is None:
            return
        try:
            self._file_storage.delete_session(session_id)
        except OSError as exc:
            logger.warning("ファイル削除失敗 session=%s: %s", session_id, exc)
        # checkpointer 内の state はそのまま残る (MemorySaver の API では削除困難)
        # session_id が再利用されない限り無害
        logger.info("session reset session_id=%s", session_id)

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if now - s.last_event_at > self._ttl]
        for sid in expired:
            self.reset(sid)

    # --------- graph state helpers ---------

    def get_state(self, session_id: str) -> dict[str, Any]:
        """checkpointer から最新 state snapshot を取得する。"""
        config = {"configurable": {"thread_id": session_id}}
        snap = self.compiled_graph.get_state(config)
        return snap.values if snap else {}

    async def update_state(self, session_id: str, values: dict[str, Any]) -> None:
        """checkpointer の state を更新する (HITL 承認結果を反映するため)。"""
        config = {"configurable": {"thread_id": session_id}}
        # aupdate_state は async API
        await self.compiled_graph.aupdate_state(config, values)
