"""手数料計算結果のサマリ生成。

取引先別・商材別の合計と全体 KPI を返す。
"""

from __future__ import annotations

from collections import defaultdict


def generate_summary(results: list[dict]) -> dict:
    """全体サマリを返す。

    Args:
        results: calculate_commission の戻り値リスト。

    Returns:
        {
            "total_records": int,
            "auto_completed": int,        # is_anomaly=False かつ master_found=True
            "hitl_pending": int,           # is_anomaly=True
            "error_count": int,            # error_message あり
            "total_commission_amount": int,
            "auto_completion_rate": float, # 0.0 - 1.0
            "by_partner": [...],
            "by_product": [...],
        }
    """
    total_records = len(results)
    auto_completed = 0
    hitl_pending = 0
    error_count = 0
    total_amount = 0

    partner_totals: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "total": 0}
    )
    product_totals: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "total": 0}
    )

    for r in results:
        amount = int(r.get("total_commission", 0) or 0)
        total_amount += amount

        if r.get("error_message"):
            error_count += 1
        if r.get("is_anomaly"):
            hitl_pending += 1
        else:
            auto_completed += 1

        partner_key = (
            r.get("partner_name") or f"取引先{r.get('partner_code', 'unknown')}"
        )
        partner_totals[partner_key]["count"] += 1
        partner_totals[partner_key]["total"] += amount

        product_key = r.get("product") or "(不明)"
        product_totals[product_key]["count"] += 1
        product_totals[product_key]["total"] += amount

    by_partner = [
        {"name": name, "count": v["count"], "total": v["total"]}
        for name, v in sorted(
            partner_totals.items(), key=lambda kv: kv[1]["total"], reverse=True
        )
    ]
    by_product = [
        {"name": name, "count": v["count"], "total": v["total"]}
        for name, v in sorted(
            product_totals.items(), key=lambda kv: kv[1]["total"], reverse=True
        )
    ]

    rate = auto_completed / total_records if total_records else 0.0

    return {
        "total_records": total_records,
        "auto_completed": auto_completed,
        "hitl_pending": hitl_pending,
        "error_count": error_count,
        "total_commission_amount": total_amount,
        "auto_completion_rate": rate,
        "by_partner": by_partner,
        "by_product": by_product,
    }
