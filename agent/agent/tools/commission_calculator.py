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
"""コミッション計算ルールエンジン (Pure Python, LLM 不使用)。

サンプルデータ検証 (2026-05) で確認した重要事項:
- master.基本コミッション は yen 固定額（販売価格 × 率 ではない）
- 配送個数は通常 1。戻入条件は本数ベース（12 本未満 / 24 本未満）
- マスタの複合キーは ``{一次店コード:10}{申込月:YYYYMMDD}{商材}{決済方法}``
- 突合に使うのは sales 側の「（Rename）商材」「（Rename）決済方法」「（Rename）取引先コード」
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

try:
    from agent.agent.tools.excel_parser import normalize_yyyymmdd  # type: ignore
except ImportError:
    # tools/ ディレクトリを直接 sys.path に入れた場合の fallback (smoke test 用)
    from excel_parser import normalize_yyyymmdd  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

# HITL 対象とする金額閾値（円）。Config 側から上書き可能だが、デフォルトはここ。
DEFAULT_HIGH_AMOUNT_THRESHOLD = 100_000

ZERO = Decimal("0")


def _to_decimal(value: Any) -> Decimal:
    """任意の値を Decimal に変換する。None / 空文字 / 不正値はゼロ扱い。"""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        # Excel 由来でブール扱いされた値もゼロに寄せる
        return Decimal(1) if value else ZERO
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return ZERO
    if isinstance(value, str):
        s = value.strip().replace(",", "").replace("¥", "").replace("円", "")
        if not s:
            return ZERO
        try:
            return Decimal(s)
        except InvalidOperation:
            return ZERO
    return ZERO


def _is_truthy_flag(value: Any) -> bool:
    """マスタ / 売上のフラグ列が有効か判定する。

    None / 0 / 空文字 / "なし" / "無効" などはすべて False 扱い。
    数値・"あり"・"対象" などは True 扱い。
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        s = value.strip()
        if not s or s in {"0", "なし", "無効", "対象外", "未適用", "－", "-"}:
            return False
        return True
    return True


def build_master_key(record: dict[str, Any]) -> str | None:
    """売上明細レコードから取引条件マスタの複合キーを構築する。

    マスタ側のキー形式 (フォーカスタマーズ検証で確定):
        ``{一次店コード}{申込月YYYYMMDD}{（Rename）商材}{（Rename）決済方法}``

    必須要素のいずれかが欠ける場合は ``None`` を返す（master_not_found 扱い）。
    """
    primary_code = record.get("（Rename）取引先コード") or record.get("獲得者ID")
    apply_month_raw = record.get("申込月")
    product = record.get("（Rename）商材")
    payment = record.get("（Rename）決済方法")

    apply_month = normalize_yyyymmdd(apply_month_raw)

    if any(v is None or v == "" for v in (primary_code, apply_month, product, payment)):
        return None

    # 一次店コードが int の場合 str() しても 10 桁数字になる前提
    return f"{primary_code}{apply_month}{product}{payment}"


def _return_amount(
    delivery_count: int,
    master: dict[str, Any],
    basic_amount: Decimal,
) -> tuple[Decimal, str]:
    """戻入手数料を計算する (マイナス値で返す)。

    サンプルマスタでは戻入条件 = 本数、戻入全額条件 = "12本未満"、戻入半額条件 = "24本未満"。
    配送個数が条件を満たすときに基本コミッション分の全額 / 半額をマイナスとして加算する。
    `違約金` は別途加減（サンプルでは ALL NULL のため通常はゼロ）。
    """
    cond = master.get("戻入条件")
    if cond != "本数":
        return ZERO, "戻入条件='本数'以外は未対応"

    full_threshold = _parse_count_threshold(master.get("戻入全額条件"))
    half_threshold = _parse_count_threshold(master.get("戻入半額条件"))

    if full_threshold is not None and delivery_count < full_threshold:
        # 全額戻入: 基本コミッションを全額マイナス
        return -basic_amount, f"配送個数 {delivery_count} 本 < 全額閾値 {full_threshold} → 全額戻入"
    if half_threshold is not None and delivery_count < half_threshold:
        # 半額戻入: 基本コミッションの半額をマイナス
        half = (basic_amount / Decimal(2)).quantize(Decimal("1"))
        return -half, f"配送個数 {delivery_count} 本 < 半額閾値 {half_threshold} → 半額戻入"

    return ZERO, f"配送個数 {delivery_count} 本 → 戻入なし"


def _parse_count_threshold(value: Any) -> int | None:
    """"12本未満" のような文字列から数値部分を抽出する。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        digits = "".join(c for c in value if c.isdigit())
        if digits:
            try:
                return int(digits)
            except ValueError:
                return None
    return None


def calculate_commission(
    record: dict[str, Any],
    master: dict[str, Any] | None,
    high_amount_threshold: int = DEFAULT_HIGH_AMOUNT_THRESHOLD,
) -> dict[str, Any]:
    """売上明細 1 件に対して取引条件マスタを参照し手数料を計算する。

    LLM は使わず Pure Python で実装。各ステップの計算根拠は ``calculation_trace``
    に日本語で蓄積される。
    """
    trace: list[str] = []
    record_no = record.get("レコードNo（手数料明細用）") or record.get("レコードNo")

    # =====================================================================
    # ステップ1: マスタ参照
    # =====================================================================
    # 売上明細から複合キーを構築し、取引条件マスタを引く。
    # キーが構築不能 or マスタに該当キーが無い場合は HITL 対象として早期 return。
    master_key = build_master_key(record)
    trace.append(f"ステップ1: マスタキー構築 → {master_key!r}")

    if master_key is None or master is None:
        trace.append("ステップ1: 売上側にキー要素が不足、または master が未読込")
        return _build_unmatched_result(record, trace, status="master_not_found", high_amount_threshold=high_amount_threshold)

    if master_key not in (master or {}):
        trace.append(f"ステップ1: マスタにキー {master_key!r} が存在しない → HITL 対象")
        return _build_unmatched_result(record, trace, status="master_not_found", master_key=master_key, high_amount_threshold=high_amount_threshold)

    master_row = master[master_key]
    trace.append(f"ステップ1: マスタヒット 取引先名称={master_row.get('取引先名称')!r}")

    try:
        # =================================================================
        # ステップ2: 基本コミッション
        # =================================================================
        # マスタの「基本コミッション」列は yen 固定額。販売価格 × 率ではない
        # （サンプル検証で 10000〜47000 円の固定値が確認されている）。
        basic_commission = _to_decimal(master_row.get("基本コミッション"))
        trace.append(f"ステップ2: 基本コミッション = {basic_commission} 円 (マスタ固定値)")

        # =================================================================
        # ステップ3: ボリュームインセンティブ
        # =================================================================
        # マスタの「配送周期インセンフラグ」が立っている、もしくは
        # 「ボリュームインセンティブ」列に値があれば加算する。
        # サンプルでは大半 0 円。
        volume_incentive = _to_decimal(master_row.get("ボリュームインセンティブ"))
        if _is_truthy_flag(master_row.get("配送周期インセンフラグ")):
            trace.append(f"ステップ3: 配送周期インセンフラグ ON → ボリュームインセンティブ {volume_incentive} 円 加算")
        else:
            trace.append(f"ステップ3: ボリュームインセンティブ = {volume_incentive} 円")

        # =================================================================
        # ステップ4: 特別コミッション① と特別コミッション②
        # =================================================================
        # マスタの両列を別々に加算する。どちらも 0 のことが多い。
        special_1 = _to_decimal(master_row.get("特別コミッション"))
        special_2 = _to_decimal(master_row.get("特別コミッション②"))
        trace.append(f"ステップ4: 特別コミッション① = {special_1} 円 / 特別コミッション② = {special_2} 円")

        # =================================================================
        # ステップ5: 25・37 ヶ月目以降継続コミッション
        # =================================================================
        # マスタの「25・37ヶ月目以降継続コミッションフラグ」が ON かつ
        # 売上側の「25ヶ月以降適用継続コミッション」フラグがセットされている場合のみ
        # 「継続コミッション」を加算する。サンプルでは sales 側 ALL NULL。
        continuous_commission = ZERO
        master_flag = _is_truthy_flag(master_row.get("25・37ヶ月目以降継続コミッションフラグ"))
        sales_flag = _is_truthy_flag(record.get("25ヶ月以降適用継続コミッション"))
        if master_flag and sales_flag:
            continuous_commission = _to_decimal(master_row.get("継続コミッション"))
            trace.append(f"ステップ5: 継続コミッションフラグ ON × 売上フラグ ON → {continuous_commission} 円 加算")
        else:
            trace.append("ステップ5: 継続コミッション該当なし (フラグ未一致)")

        # =================================================================
        # ステップ6: 紹介制度コミッション
        # =================================================================
        # 売上側に「紹介制度区分」がセットされ、マスタ側にも該当する区分の
        # 紹介制度コミッションが定義されていれば加算する。サンプルでは sales 側 ALL NULL。
        referral_commission = ZERO
        sales_referral_kind = record.get("紹介制度区分")
        master_referral_kind = master_row.get("紹介制度区分")
        if sales_referral_kind:
            if master_referral_kind and str(master_referral_kind) == str(sales_referral_kind):
                referral_commission = _to_decimal(master_row.get("紹介制度コミッション"))
                trace.append(
                    f"ステップ6: 紹介制度区分 {sales_referral_kind!r} 一致 → {referral_commission} 円 加算"
                )
            else:
                trace.append(
                    f"ステップ6: 売上に紹介制度区分 {sales_referral_kind!r} 有 / マスタは {master_referral_kind!r} → 不一致のため加算なし"
                )
        else:
            trace.append("ステップ6: 売上側に紹介制度区分なし → 加算なし")

        # =================================================================
        # ステップ7: PAP / PAS / PH (=6L) コミッション
        # =================================================================
        # 売上側区分セット + マスタ側コミッション > 0 のときに加算。
        # サンプルでは sales 側 PAP/PAS/PH 区分はすべて NULL。
        # PH 区分はマスタには無く、6L 区分が相当する可能性が高いため両方マッピング。
        pap_commission, pap_note = _calc_optional_commission(
            record.get("PAP区分"), master_row.get("PAP区分"), master_row.get("PAPコミッション"), "PAP"
        )
        pas_commission, pas_note = _calc_optional_commission(
            record.get("PAS区分"), master_row.get("PAS区分"), master_row.get("PASコミッション"), "PAS"
        )
        # PH は 6L エイリアス
        ph_commission, ph_note = _calc_optional_commission(
            record.get("PH区分"), master_row.get("6L区分"), master_row.get("6Lコミッション"), "PH(=6L)"
        )
        trace.append(f"ステップ7: PAP={pap_commission} 円 ({pap_note})")
        trace.append(f"ステップ7: PAS={pas_commission} 円 ({pas_note})")
        trace.append(f"ステップ7: PH={ph_commission} 円 ({ph_note})")

        # =================================================================
        # ステップ8: QI 分割計上 (按分)
        # =================================================================
        # マスタの QI 適用範囲 + QI 分割計上期間で按分計算。
        # 期間 N ヶ月の場合、基本+特別系の合計を N で割る。
        # サンプルでは master の QI 関連列は概ね NULL のため、デフォルトは按分なし。
        qi_amount = ZERO
        qi_range = master_row.get("QI適用範囲")
        qi_period = master_row.get("QI分割計上期間")
        if _is_truthy_flag(qi_range) and qi_period:
            period_n = _parse_count_threshold(qi_period) or _to_decimal(qi_period)
            try:
                period_dec = Decimal(period_n) if isinstance(period_n, int) else _to_decimal(qi_period)
            except (InvalidOperation, TypeError):
                period_dec = ZERO
            if period_dec > 0:
                qi_base = basic_commission + special_1 + special_2
                qi_amount = (qi_base / period_dec).quantize(Decimal("1"))
                trace.append(
                    f"ステップ8: QI適用 範囲={qi_range!r} 期間={qi_period} ヶ月 → 月次按分 {qi_amount} 円"
                )
            else:
                trace.append(f"ステップ8: QI期間={qi_period!r} が不正、按分計算スキップ")
        else:
            trace.append("ステップ8: QI 分割計上の対象外")

        # =================================================================
        # ステップ9: 口振分割時初回手数料
        # =================================================================
        # マスタの「口振分割フラグ」が ON、または売上側「口振初回手数料」に値がある場合、
        # マスタの「口振分割時初回手数料」を加算する。
        debit_initial_fee = ZERO
        if _is_truthy_flag(master_row.get("口振分割フラグ")):
            debit_initial_fee = _to_decimal(master_row.get("口振分割時初回手数料"))
            trace.append(f"ステップ9: 口振分割フラグ ON → 初回手数料 {debit_initial_fee} 円 加算")
        elif record.get("口振初回手数料") is not None:
            debit_initial_fee = _to_decimal(record.get("口振初回手数料"))
            trace.append(f"ステップ9: 売上側 口振初回手数料 = {debit_initial_fee} 円 を採用")
        else:
            trace.append("ステップ9: 口振分割初回手数料 該当なし")

        # =================================================================
        # ステップ10: 戻入条件 (12本未満全額 / 24本未満半額) + 違約金
        # =================================================================
        # 戻入は契約解約時に発生する clawback。解約日が未セットなら適用しない。
        # サンプルデータでは 解約日 ALL NULL のため、通常は戻入なし。
        cancellation_date = record.get("解約日")
        delivery_count_raw = record.get("配送個数")
        delivery_count = int(delivery_count_raw) if isinstance(delivery_count_raw, (int, float)) else 0
        penalty = _to_decimal(master_row.get("違約金"))

        if cancellation_date is None:
            return_amount = ZERO
            trace.append(f"ステップ10: 解約日なし → 戻入適用外 (配送個数 {delivery_count} 本は将来戻入の可能性あり)")
        else:
            return_amount, return_note = _return_amount(delivery_count, master_row, basic_commission)
            if penalty > 0:
                return_amount = return_amount - penalty
                trace.append(f"ステップ10: 解約日 {cancellation_date} / {return_note} / 違約金 {penalty} 円も控除")
            else:
                trace.append(f"ステップ10: 解約日 {cancellation_date} / {return_note} / 違約金なし")

        # =================================================================
        # 合計
        # =================================================================
        total_commission = (
            basic_commission
            + volume_incentive
            + special_1
            + special_2
            + continuous_commission
            + referral_commission
            + pap_commission
            + pas_commission
            + ph_commission
            + debit_initial_fee
            + return_amount
        )
        trace.append(f"合計コミッション = {total_commission} 円")

        # =================================================================
        # 異常検知 (HITL 振り分けの初期判定。最終判定は anomaly_detector が担う)
        # =================================================================
        is_anomaly = total_commission > Decimal(high_amount_threshold)
        if is_anomaly:
            trace.append(
                f"異常: 合計 {total_commission} 円 > 閾値 {high_amount_threshold} 円 → HITL 候補"
            )

        return {
            "record_no": record_no,
            "取引先コード": record.get("（Rename）取引先コード") or record.get("獲得者ID"),
            "取引先名称": master_row.get("取引先名称"),
            "商材": record.get("（Rename）商材"),
            "決済方法": record.get("（Rename）決済方法"),
            "basic_commission": basic_commission,
            "volume_incentive": volume_incentive,
            "special_commission_1": special_1,
            "special_commission_2": special_2,
            "continuous_commission": continuous_commission,
            "referral_commission": referral_commission,
            "pap_commission": pap_commission,
            "pas_commission": pas_commission,
            "ph_commission": ph_commission,
            "qi_amount": qi_amount,
            "debit_initial_fee": debit_initial_fee,
            "return_amount": return_amount,
            "total_commission": total_commission,
            "master_key_used": master_key,
            "calculation_trace": trace,
            "master_found": True,
            "is_anomaly": is_anomaly,
            "status": "ok" if not is_anomaly else "high_amount",
        }

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "calculate_commission 失敗 record_no=%s key=%s", record_no, master_key
        )
        trace.append(f"計算エラー: {type(exc).__name__}: {exc}")
        return _build_unmatched_result(
            record,
            trace,
            status="calc_error",
            master_key=master_key,
            error=str(exc),
            high_amount_threshold=high_amount_threshold,
        )


def _calc_optional_commission(
    sales_kind: Any,
    master_kind: Any,
    master_amount: Any,
    label: str,
) -> tuple[Decimal, str]:
    """PAP / PAS / PH 系のオプションコミッションを計算する共通ロジック。

    Returns:
        (金額, トレースメッセージ)
    """
    if not sales_kind:
        return ZERO, f"売上側 {label} 区分なし"
    if not master_kind:
        return ZERO, f"マスタ側 {label} 区分なし"
    if str(sales_kind) != str(master_kind):
        return ZERO, f"区分不一致 売上={sales_kind!r} マスタ={master_kind!r}"
    amount = _to_decimal(master_amount)
    return amount, f"区分一致 {sales_kind!r} → {amount} 円"


def _build_unmatched_result(
    record: dict[str, Any],
    trace: list[str],
    *,
    status: str,
    master_key: str | None = None,
    error: str | None = None,
    high_amount_threshold: int = DEFAULT_HIGH_AMOUNT_THRESHOLD,  # noqa: ARG001
) -> dict[str, Any]:
    """マスタ未ヒット / 計算エラー時の共通レスポンス。

    HITL 必須レコードとして ``master_found=False``, ``is_anomaly=True`` を返す。
    """
    return {
        "record_no": record.get("レコードNo（手数料明細用）") or record.get("レコードNo"),
        "取引先コード": record.get("（Rename）取引先コード") or record.get("獲得者ID"),
        "取引先名称": None,
        "商材": record.get("（Rename）商材"),
        "決済方法": record.get("（Rename）決済方法"),
        "basic_commission": ZERO,
        "volume_incentive": ZERO,
        "special_commission_1": ZERO,
        "special_commission_2": ZERO,
        "continuous_commission": ZERO,
        "referral_commission": ZERO,
        "pap_commission": ZERO,
        "pas_commission": ZERO,
        "ph_commission": ZERO,
        "qi_amount": ZERO,
        "debit_initial_fee": ZERO,
        "return_amount": ZERO,
        "total_commission": ZERO,
        "master_key_used": master_key,
        "calculation_trace": trace,
        "master_found": False,
        "is_anomaly": True,
        "status": status,
        "error": error,
    }
