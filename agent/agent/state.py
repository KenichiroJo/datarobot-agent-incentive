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
"""コミッション計算 LangGraph ワークフロー用の State 定義。

``MessagesState`` を継承し、``messages`` の add_messages reducer を保持しつつ、
commission 固有のフィールド（売上・マスタ・計算結果・HITL 候補など）を載せる。
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import MessagesState

# processing_status が取り得る値（FastAPI 側 SSE と整合させる用の定数）
STATUS_IDLE = "idle"
STATUS_PARSING = "parsing"
STATUS_CALCULATING = "calculating"
STATUS_AWAITING_HITL = "awaiting_hitl"
STATUS_APPROVING = "approving"
STATUS_EXPLAINING = "explaining"
STATUS_DONE = "done"
STATUS_ERROR = "error"

# Supervisor が conditional edge に渡すルーティング値
ROUTE_PARSE = "parse"
ROUTE_CALCULATE = "calculate"
ROUTE_REVIEW = "review"
ROUTE_APPROVE = "approve"
ROUTE_EXPLAIN = "explain"
ROUTE_END = "end"


class CommissionState(MessagesState):
    """コミッション計算ワークフロー全体で共有される state。

    LangGraph 1.x の TypedDict ベース。 ``MessagesState`` から ``messages`` を継承し
    `add_messages` reducer によりノード間の追記がマージされる。
    その他のフィールドは last-write-wins (デフォルト reducer)。
    """

    # --- ファイル取り込み ---
    # [{file_id, filename, detected_type: 'sales'|'master', path}]
    uploaded_files: list[dict[str, Any]]

    # --- パース済みデータ ---
    sales_records: list[dict[str, Any]]
    # 複合キー -> マスタ行
    master_records: dict[str, dict[str, Any]]

    # --- 計算フェーズ ---
    calculation_results: list[dict[str, Any]]
    pending_hitl: list[dict[str, Any]]
    approved_results: list[dict[str, Any]]
    summary: dict[str, Any]

    # --- ワークフロー制御 ---
    processing_status: str
    error_message: str | None
    # supervisor が判定したルーティング先（conditional edge で読む）
    next_node_hint: str | None
    # 異常検知の閾値（FastAPI 側 Config から渡せるようにする）
    anomaly_threshold: int
