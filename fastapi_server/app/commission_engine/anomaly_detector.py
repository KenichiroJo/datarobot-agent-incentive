"""異常レコード検出と HITL 対象抽出。

ルール:
- master_found == False → マスタキー不一致 (HITL 必須)
- total_commission > threshold → 高額アラート
- error_message があれば計算エラー
"""

from __future__ import annotations


def detect_anomalies(results: list[dict], threshold: int = 100_000) -> list[dict]:
    """異常レコードを抽出し hitl_reason を付加する。

    in-place で各 result の is_anomaly / hitl_reason を更新する。
    抽出されたレコードのリスト（HITL 対象）を返す。
    """
    pending: list[dict] = []
    for r in results:
        reasons: list[str] = []

        if not r.get("master_found", True):
            reasons.append("マスタキー不一致")

        if r.get("error_message"):
            reasons.append(f"計算エラー: {r['error_message']}")

        total = r.get("total_commission", 0) or 0
        if total > threshold:
            reasons.append(f"高額アラート (合計 {total:,} 円 > 閾値 {threshold:,} 円)")

        if reasons:
            r["is_anomaly"] = True
            r["hitl_reason"] = " / ".join(reasons)
            pending.append(r)
        else:
            r["is_anomaly"] = False
            r["hitl_reason"] = None

    return pending
