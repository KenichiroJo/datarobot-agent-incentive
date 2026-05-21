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
"""HITL (Human-in-the-Loop) 振り分け判定。

calculate_commission の結果リストを走査し、以下のいずれかに該当するレコードを
``pending_hitl`` として抽出する:
- master_found == False        → マスタキー不一致 (HITL 必須)
- total_commission > 閾値      → 高額アラート
- status == "calc_error"       → 計算エラー
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_HIGH_AMOUNT_THRESHOLD = 100_000

# HITL 理由の正規化キー
REASON_MASTER_NOT_FOUND = "master_not_found"
REASON_HIGH_AMOUNT = "high_amount"
REASON_CALC_ERROR = "calc_error"


def _reason_label_ja(reason: str) -> str:
    if reason == REASON_MASTER_NOT_FOUND:
        return "マスタキー不一致"
    if reason == REASON_HIGH_AMOUNT:
        return "高額アラート"
    if reason == REASON_CALC_ERROR:
        return "計算エラー"
    return reason


def detect_anomalies(
    results: list[dict[str, Any]],
    threshold: int = DEFAULT_HIGH_AMOUNT_THRESHOLD,
) -> list[dict[str, Any]]:
    """HITL 対象レコードを抽出して返す。

    Args:
        results: ``calculate_commission`` の戻り値リスト。
        threshold: 高額アラート発火の閾値 (円)。

    Returns:
        HITL 候補レコードのリスト。各レコードには ``hitl_reason``（英）と
        ``hitl_reason_ja``（日本語）が付加される。
    """
    flagged: list[dict[str, Any]] = []

    for r in results:
        reason: str | None = None

        # マスタ未ヒットは無条件で HITL 必須
        if not r.get("master_found", False):
            reason = REASON_MASTER_NOT_FOUND
        # 計算エラー
        elif r.get("status") == "calc_error":
            reason = REASON_CALC_ERROR
        # 高額アラート
        else:
            total = r.get("total_commission", Decimal(0))
            if isinstance(total, Decimal) and total > Decimal(threshold):
                reason = REASON_HIGH_AMOUNT
            elif isinstance(total, (int, float)) and total > threshold:
                reason = REASON_HIGH_AMOUNT

        if reason is not None:
            flagged.append({**r, "hitl_reason": reason, "hitl_reason_ja": _reason_label_ja(reason)})

    logger.info(
        "anomaly_detector: total=%d / flagged=%d (threshold=%d 円)",
        len(results),
        len(flagged),
        threshold,
    )
    return flagged
