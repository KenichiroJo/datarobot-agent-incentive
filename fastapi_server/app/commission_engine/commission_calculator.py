"""手数料計算ルールエンジン (Pure Python, LLM 不使用)。

指示書 Step 5 の 10 ステップに従いマスタ参照で計算する。
計算は Decimal で行い、最終的に円単位で整数に丸める。
各ステップで calculation_trace に日本語の根拠を追記する。

注意: 本実装は MVP。実運用の詳細な計算式が判明したら個別ステップを差し替える前提。
"""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _d(val: Any) -> Decimal:
    """安全に Decimal 化。NaN/None は 0。"""
    if val is None:
        return Decimal(0)
    try:
        s = str(val)
        if s.lower() in ("nan", "none", ""):
            return Decimal(0)
        return Decimal(s)
    except Exception:
        return Decimal(0)


def _round_yen(val: Decimal) -> int:
    """円単位（小数点以下切り捨てて整数）。"""
    return int(val.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# 戻入条件の本数閾値抽出 (例: '12本未満' -> 12)
_RETURN_RE = re.compile(r"(\d+)本未満")


def _parse_return_threshold(condition: str | None) -> int | None:
    if not condition:
        return None
    m = _RETURN_RE.search(condition)
    return int(m.group(1)) if m else None


def calculate_commission(record: dict, master: dict) -> dict:
    """1 レコードの手数料を計算する。

    Args:
        record: parse_sales_excel が返した辞書。
        master: 複合キー -> マスタレコード辞書のマップ。

    Returns:
        計算結果辞書。CommissionResult schema に準拠。
    """
    trace: list[str] = []
    lookup_key = record.get("lookup_key", "")
    delivery_count = int(record.get("delivery_count", 0) or 0)

    # Step 1: マスタ Lookup
    m = master.get(lookup_key)
    if m is None:
        trace.append(
            f"Step1: 複合キー {lookup_key!r} がマスタに見つかりませんでした。計算をスキップします。"
        )
        return {
            "record_no": record.get("record_no", 0),
            "partner_code": record.get("partner_code", 0),
            "partner_name": None,
            "product": record.get("product_name", ""),
            "payment_method": record.get("payment_method", ""),
            "basic_commission": 0,
            "volume_incentive": 0,
            "special_commission_1": 0,
            "special_commission_2": 0,
            "continuous_commission": 0,
            "referral_commission": 0,
            "pap_commission": 0,
            "pas_commission": 0,
            "ph_commission": 0,
            "qi_amount": 0,
            "debit_initial_fee": 0,
            "return_amount": 0,
            "total_commission": 0,
            "master_key_used": lookup_key,
            "calculation_trace": trace,
            "master_found": False,
            "is_anomaly": True,
            "hitl_reason": "マスタキー不一致",
            "error_message": None,
        }

    trace.append(
        f"Step1: マスタヒット — 取引先={m.get('partner_name')} / 商材={m.get('product')} / 決済={m.get('payment_method')}"
    )

    total = Decimal(0)

    # Step 2: 基本コミッション
    basic = _d(m.get("basic_commission"))
    total += basic
    trace.append(f"Step2: 基本コミッション = {basic} 円")

    # Step 3: ボリュームインセンティブ
    volume = _d(m.get("volume_incentive"))
    if volume > 0:
        total += volume
        trace.append(f"Step3: ボリュームインセンティブ = +{volume} 円")
    else:
        trace.append("Step3: ボリュームインセンティブ = 0 (加算なし)")

    # Step 4: 特別コミッション ① ②
    special1 = _d(m.get("special_commission_1"))
    special2 = _d(m.get("special_commission_2"))
    total += special1 + special2
    trace.append(
        f"Step4: 特別コミッション① = +{special1} 円, ② = +{special2} 円"
    )

    # Step 5: 25・37 ヶ月以降継続コミッション
    cont_flag = _d(m.get("continuous_flag_25_37"))
    cont = _d(m.get("continuous_commission"))
    if cont_flag != 0 and cont > 0:
        total += cont
        trace.append(
            f"Step5: 25/37ヶ月以降継続フラグ立 → 継続コミッション = +{cont} 円"
        )
    else:
        trace.append("Step5: 継続コミッション = 0 (フラグ立たず)")

    # Step 6: 紹介制度コミッション
    referral = _d(m.get("referral_commission"))
    if referral > 0:
        total += referral
        trace.append(f"Step6: 紹介制度コミッション = +{referral} 円")
    else:
        trace.append("Step6: 紹介制度コミッション = 0")

    # Step 7: PAP / PAS / PH
    pap = _d(m.get("pap_commission"))
    pas = _d(m.get("pas_commission"))
    ph = _d(m.get("ph_commission"))
    total += pap + pas + ph
    trace.append(
        f"Step7: PAP = +{pap} 円, PAS = +{pas} 円, PH(6L/デリキチ) = +{ph} 円"
    )

    # Step 8: QI 分割計上
    qi_scope = _d(m.get("qi_scope"))
    qi_period = _d(m.get("qi_split_period"))
    qi_amount = Decimal(0)
    if qi_scope > 0 and qi_period > 0:
        # 簡易実装: QI 適用範囲を分割計上期間で割って当月按分
        qi_amount = (qi_scope / qi_period).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        total += qi_amount
        trace.append(
            f"Step8: QI 分割計上 = {qi_scope} ÷ {qi_period} = +{qi_amount} 円/月"
        )
    else:
        trace.append("Step8: QI 分割計上対象外")

    # Step 9: 口振分割初回手数料
    debit_initial = _d(m.get("debit_initial_fee"))
    payment_method = record.get("payment_method", "")
    if debit_initial > 0 and ("口振" in payment_method or "口座振替" in payment_method):
        total += debit_initial
        trace.append(
            f"Step9: 口座振替 → 初回手数料 = +{debit_initial} 円"
        )
    else:
        trace.append("Step9: 口振分割対象外 (加算なし)")

    # Step 10: 戻入条件チェック (12本未満=全額 / 24本未満=半額)
    # 暫定仕様: ファイル区分に「初回」が含まれる売上明細は戻入対象外
    # (戻入は継続購入数を基準に判定するため、初回出荷時には未確定)
    return_amount = Decimal(0)
    full_threshold = _parse_return_threshold(m.get("return_full_condition"))
    half_threshold = _parse_return_threshold(m.get("return_half_condition"))
    penalty = _d(m.get("penalty"))
    file_kbn = str(record.get("ファイル区分", "") or "")
    is_initial = "初回" in file_kbn
    if is_initial:
        trace.append(
            f"Step10: ファイル区分={file_kbn} は初回出荷のため戻入対象外"
        )
    elif full_threshold and delivery_count < full_threshold:
        # 全額戻入: total を反転 + 違約金
        return_amount = -(total + penalty)
        trace.append(
            f"Step10: 配送個数 {delivery_count} 本 < {full_threshold} 本 → "
            f"戻入全額 ({-total} 円) + 違約金 ({-penalty} 円)"
        )
        total += return_amount
    elif half_threshold and delivery_count < half_threshold:
        # 半額戻入
        return_amount = -(total / Decimal(2))
        return_amount = return_amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        trace.append(
            f"Step10: 配送個数 {delivery_count} 本 < {half_threshold} 本 → "
            f"戻入半額 ({return_amount} 円)"
        )
        total += return_amount
    elif not is_initial:
        trace.append(
            f"Step10: 配送個数 {delivery_count} 本 — 戻入対象外"
        )

    total_yen = _round_yen(total)
    trace.append(f"=== 合計手数料 = {total_yen} 円 ===")

    return {
        "record_no": record.get("record_no", 0),
        "partner_code": record.get("partner_code", 0),
        "partner_name": m.get("partner_name"),
        "product": record.get("product_name", ""),
        "payment_method": record.get("payment_method", ""),
        "basic_commission": int(basic),
        "volume_incentive": int(volume),
        "special_commission_1": int(special1),
        "special_commission_2": int(special2),
        "continuous_commission": int(cont) if cont_flag != 0 else 0,
        "referral_commission": int(referral),
        "pap_commission": int(pap),
        "pas_commission": int(pas),
        "ph_commission": int(ph),
        "qi_amount": int(qi_amount),
        "debit_initial_fee": int(debit_initial)
        if (debit_initial > 0 and ("口振" in payment_method or "口座振替" in payment_method))
        else 0,
        "return_amount": int(return_amount),
        "total_commission": total_yen,
        "master_key_used": lookup_key,
        "calculation_trace": trace,
        "master_found": True,
        "is_anomaly": False,
        "hitl_reason": None,
        "error_message": None,
    }
