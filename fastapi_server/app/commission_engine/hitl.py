"""HITL 承認の適用ロジック（LLM/LangGraph 不使用）。

計算結果リストと承認決定リストから、確定データ（approved_results）を生成する。
"""

from __future__ import annotations


def apply_hitl_decisions(results: list[dict], decisions: list[dict]) -> list[dict]:
    """HITL 決定を反映して確定データを返す。

    - 異常なし (is_anomaly=False) のレコードは自動的に確定に含める
    - 異常ありのレコードは decisions に従う:
      - action="approve": そのまま確定
      - action="manual":  manual_amount で total_commission を上書きして確定
      - action="reject":  確定に含めない
      - 決定が無い異常レコードは確定に含めない
    """
    dmap = {
        d["record_no"]: d for d in decisions if isinstance(d, dict) and "record_no" in d
    }
    approved: list[dict] = []
    for r in results:
        if not r.get("is_anomaly"):
            approved.append(r)
            continue

        d = dmap.get(r.get("record_no"))
        if not d:
            continue
        action = d.get("action")
        if action == "approve":
            approved.append(r)
        elif action == "manual":
            amount = d.get("manual_amount")
            if amount is not None:
                r2 = dict(r)
                r2["total_commission"] = int(amount)
                r2["is_anomaly"] = False
                r2["hitl_reason"] = (
                    f"手動入力: {amount} 円 (元: {r.get('total_commission')})"
                )
                approved.append(r2)
        # action == "reject" は確定に含めない
    return approved
