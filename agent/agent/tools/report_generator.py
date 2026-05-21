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
"""コミッション計算結果のサマリー生成。

取引先別 / 商材別 / 全体合計 / HITL 件数 / 自動完了件数 を集計する。
DashboardPage の KPI / 集計テーブル / ドーナツチャートのデータ供給源。
"""
from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

ZERO = Decimal("0")


def _decimal_to_int(value: Any) -> int:
    """Decimal / int / float / None を int に変換 (端数は四捨五入)。"""
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value.to_integral_value())
    if isinstance(value, (int, float)):
        return int(round(value))
    return 0


def generate_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """計算結果のサマリーを生成する。

    Args:
        results: ``calculate_commission`` の戻り値リスト (HITL 確定後でも未確定でも可)。

    Returns:
        サマリー辞書:
          - kpi: 全体件数 / 自動完了 / HITL 残 / 合計金額 / 自動完了率
          - by_partner: 取引先別合計 (件数 + 合計金額)
          - by_product: 商材別合計 (件数 + 合計金額)
          - by_status: ステータス別件数
    """
    total_records = len(results)
    auto_completed = 0
    hitl_pending = 0
    hitl_approved = 0
    error_count = 0
    total_commission = ZERO

    by_partner: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"partner": "", "record_count": 0, "total_commission": ZERO}
    )
    by_product: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"product": "", "record_count": 0, "total_commission": ZERO}
    )
    by_status: dict[str, int] = defaultdict(int)

    for r in results:
        status = r.get("status", "ok")
        by_status[status] += 1
        if status == "calc_error":
            error_count += 1
        elif r.get("master_found") and not r.get("is_anomaly"):
            auto_completed += 1
        elif r.get("hitl_decided"):
            # HITL 後の確定済み (approve ノードで付与されるフラグを想定)
            hitl_approved += 1
        else:
            hitl_pending += 1

        amount = r.get("total_commission", ZERO)
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount)) if amount is not None else ZERO
        total_commission += amount

        partner_name = r.get("取引先名称") or "(未確定)"
        partner_bucket = by_partner[partner_name]
        partner_bucket["partner"] = partner_name
        partner_bucket["record_count"] += 1
        partner_bucket["total_commission"] = partner_bucket["total_commission"] + amount

        product_name = r.get("商材") or "(未確定)"
        product_bucket = by_product[product_name]
        product_bucket["product"] = product_name
        product_bucket["record_count"] += 1
        product_bucket["total_commission"] = product_bucket["total_commission"] + amount

    auto_completion_rate = (auto_completed / total_records) if total_records > 0 else 0.0

    return {
        "kpi": {
            "total_records": total_records,
            "auto_completed": auto_completed,
            "hitl_pending": hitl_pending,
            "hitl_approved": hitl_approved,
            "error_count": error_count,
            "total_commission_amount": _decimal_to_int(total_commission),
            "auto_completion_rate": round(auto_completion_rate, 4),
        },
        "by_partner": sorted(
            (
                {
                    "partner": b["partner"],
                    "record_count": b["record_count"],
                    "total_commission": _decimal_to_int(b["total_commission"]),
                }
                for b in by_partner.values()
            ),
            key=lambda x: x["total_commission"],
            reverse=True,
        ),
        "by_product": sorted(
            (
                {
                    "product": b["product"],
                    "record_count": b["record_count"],
                    "total_commission": _decimal_to_int(b["total_commission"]),
                }
                for b in by_product.values()
            ),
            key=lambda x: x["total_commission"],
            reverse=True,
        ),
        "by_status": dict(by_status),
    }
