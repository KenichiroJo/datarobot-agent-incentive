"""Excel パーサ。

売上明細 Excel と取引条件マスタ Excel を読み込み、
正規化された辞書のリスト / マップに変換する。

両 Excel ともサンプルデータ (2026-05 受領分) のスキーマに合わせて実装している。
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

import pandas as pd


# 売上明細から保持するカラム（指示書 + サンプル実列名にマッピング済み）
_SALES_KEEP_COLUMNS = [
    "No",
    "ファイル区分",
    "レコードNo（手数料明細用）",
    "契約ID",
    "申込日付",
    "申込月",
    "出荷日",
    "商材",
    "（Rename）商材",
    "出荷時決済方法",
    "（Rename）決済方法",
    "獲得者ID",
    "（Rename）取引先コード",
    "CSID",
    "獲得者名",
    "獲得店舗名",
    "配送個数",
    "販売価格_顧客",
    "基本コミッション",
    "ボリュームインセン",
    "特別コミッション",
    "特別コミッション2",
    "QI適用範囲",
    "分割計上期間",
    "口振初回手数料",
    "紹介制度区分",
    "紹介制度コミッション",
    "25ヶ月以降適用継続コミッション",
    "継続コミッション",
    "PAP区分",
    "PAPコミッション",
    "PAS区分",
    "PASコミッション",
    "PH区分",
    "PHコミッション",
    "理由",  # 既存複合キー
]


def _to_datetime(val: Any) -> datetime | None:
    """Excel 値を datetime に変換。NaN / NaT は None。"""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, pd.Timestamp):
        if pd.isna(val):
            return None
        return val.to_pydatetime()
    if isinstance(val, float) and math.isnan(val):
        return None
    try:
        ts = pd.to_datetime(val, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except Exception:
        return None


def _to_int(val: Any, default: int = 0) -> int:
    """安全に int 化。NaN は default。"""
    if val is None:
        return default
    if isinstance(val, float) and math.isnan(val):
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _to_float(val: Any, default: float = 0.0) -> float:
    """安全に float 化。NaN は default。"""
    if val is None:
        return default
    if isinstance(val, float) and math.isnan(val):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _to_str(val: Any, default: str | None = None) -> str | None:
    """安全に str 化。NaN は default。"""
    if val is None:
        return default
    if isinstance(val, float) and math.isnan(val):
        return default
    s = str(val).strip()
    return s if s else default


def _normalize_payment_method(raw: str | None) -> str:
    """出荷時決済方法（例: 'クレジット(GMO)'）を統一名（例: 'クレジットカード'）に変換。

    （Rename）決済方法列があればそれを優先するため、この関数はフォールバック用。
    """
    if not raw:
        return ""
    s = raw.strip()
    if "クレジット" in s:
        return "クレジットカード"
    if "キャリア" in s:
        return "キャリア決済"
    if "代引" in s:
        return "代引"
    if "口振" in s or "口座振替" in s:
        return "口座振替"
    return s


def make_lookup_key(
    partner_code: int,
    application_month: datetime,
    product: str,
    payment_method: str,
) -> str:
    """マスタ参照用複合キーを生成する。

    形式: {取引先コード10桁}{YYYYMMDD}{商材}{決済方法}
    日付は月初日 (YYYY-MM-01) を YYYYMMDD で連結。
    例: '201208000320260301ずっとPREMIUMプランクレジットカード'
    """
    code_part = str(int(partner_code))
    # 申込月は YYYY-MM-01 が来る想定だが、念のため月初に丸める
    first_of_month = application_month.replace(day=1)
    date_part = first_of_month.strftime("%Y%m%d")
    product_part = product.strip() if product else ""
    payment_part = payment_method.strip() if payment_method else ""
    return f"{code_part}{date_part}{product_part}{payment_part}"


def parse_sales_excel(file_path: str) -> list[dict]:
    """売上明細 Excel をパースして辞書のリストを返す。

    指定された保持カラムだけを抽出し、複合キーを再生成する。
    """
    df = pd.read_excel(
        file_path,
        sheet_name=0,
        dtype={"（Rename）取引先コード": "Int64"},
    )

    available = [c for c in _SALES_KEEP_COLUMNS if c in df.columns]
    df = df[available].copy()

    records: list[dict] = []
    for _, row in df.iterrows():
        partner_code = _to_int(row.get("（Rename）取引先コード"))
        application_month = _to_datetime(row.get("申込月"))
        product_name = _to_str(row.get("（Rename）商材"), default="") or ""
        payment_method = _to_str(row.get("（Rename）決済方法"), default="") or ""

        # 既存の「理由」列に複合キーが入っているならそれを優先、なければ再生成
        existing_key = _to_str(row.get("理由"))
        if existing_key and re.match(r"^\d{10}\d{8}", existing_key):
            lookup_key = existing_key
        elif application_month and partner_code:
            lookup_key = make_lookup_key(
                partner_code, application_month, product_name, payment_method
            )
        else:
            lookup_key = ""

        rec: dict[str, Any] = {
            "No": _to_int(row.get("No")),
            "ファイル区分": _to_str(row.get("ファイル区分")),
            "record_no": _to_int(row.get("レコードNo（手数料明細用）")),
            "contract_id": _to_int(row.get("契約ID")),
            "application_date": _to_datetime(row.get("申込日付")),
            "application_month": application_month,
            "shipping_date": _to_datetime(row.get("出荷日")),
            "product_category": _to_str(row.get("商材"), default="") or "",
            "product_name": product_name,
            "payment_method_raw": _to_str(row.get("出荷時決済方法"), default="") or "",
            "payment_method": payment_method,
            "acquirer_id": _to_int(row.get("獲得者ID")),
            "partner_code": partner_code,
            "cs_id": _to_int(row.get("CSID")),
            "acquirer_name": _to_str(row.get("獲得者名")),
            "acquirer_shop_name": _to_str(row.get("獲得店舗名")),
            "delivery_count": _to_int(row.get("配送個数")),
            "customer_price": _to_int(row.get("販売価格_顧客")),
            "lookup_key": lookup_key,
            # 売上明細側に入っている既存値も raw に保持（検証用）
            "raw": {
                "basic_commission": _to_float(row.get("基本コミッション")),
                "volume_incentive": _to_float(row.get("ボリュームインセン")),
                "special_commission_1": _to_float(row.get("特別コミッション")),
                "special_commission_2": _to_float(row.get("特別コミッション2")),
                "qi_scope": _to_float(row.get("QI適用範囲")),
                "qi_split_period": _to_float(row.get("分割計上期間")),
                "debit_initial_fee": _to_float(row.get("口振初回手数料")),
                "referral_kbn": _to_float(row.get("紹介制度区分")),
                "referral_commission": _to_float(row.get("紹介制度コミッション")),
                "continuous_25month": _to_float(row.get("25ヶ月以降適用継続コミッション")),
                "continuous_commission": _to_float(row.get("継続コミッション")),
                "pap_kbn": _to_str(row.get("PAP区分")),
                "pap_commission": _to_float(row.get("PAPコミッション")),
                "pas_kbn": _to_str(row.get("PAS区分")),
                "pas_commission": _to_float(row.get("PASコミッション")),
                "ph_kbn": _to_str(row.get("PH区分")),
                "ph_commission": _to_float(row.get("PHコミッション")),
            },
        }
        records.append(rec)
    return records


def parse_master_excel(file_path: str) -> dict[str, dict]:
    """取引条件マスタ Excel をパースして複合キーをキーとする dict を返す。"""
    df = pd.read_excel(file_path, sheet_name=0)

    records: dict[str, dict] = {}
    for _, row in df.iterrows():
        key = _to_str(row.get("キー"))
        if not key:
            continue

        partner_code = _to_int(row.get("一次店コード"))
        product = _to_str(row.get("商材"), default="") or ""
        payment_method = _to_str(row.get("決済方法"), default="") or ""

        records[key] = {
            "key": key,
            "partner_name": _to_str(row.get("取引先名称"), default="") or "",
            "primary_partner_code": partner_code,
            "commission_kbn": _to_str(row.get("コミッション区分")),
            "condition_definition": _to_str(row.get("条件適用定義")),
            "payment_definition": _to_str(row.get("支払定義")),
            "product": product,
            "payment_method": payment_method,
            "basic_commission": _to_float(row.get("基本コミッション")),
            "volume_incentive": _to_float(row.get("ボリュームインセンティブ")),
            "special_commission_1": _to_float(row.get("特別コミッション")),
            "special_commission_2": _to_float(row.get("特別コミッション②")),
            "qi_scope": _to_float(row.get("QI適用範囲")),
            "qi_split_period": _to_float(row.get("QI分割計上期間")),
            "debit_initial_fee": _to_float(row.get("口振分割時初回手数料")),
            "referral_kbn": _to_float(row.get("紹介制度区分")),
            "referral_commission": _to_float(row.get("紹介制度コミッション")),
            "continuous_flag_25_37": _to_float(
                row.get("25・37ヶ月目以降継続コミッションフラグ")
            ),
            "continuous_commission": _to_float(row.get("継続コミッション")),
            "pap_kbn": _to_str(row.get("PAP区分")),
            "pap_commission": _to_float(row.get("PAPコミッション")),
            "pas_kbn": _to_str(row.get("PAS区分")),
            "pas_commission": _to_float(row.get("PASコミッション")),
            "ph_kbn": _to_str(row.get("デリキチ区分")),
            "ph_commission": _to_float(row.get("デリキチコミッション"))
            + _to_float(row.get("6Lコミッション")),
            "return_condition": _to_str(row.get("戻入条件")),
            "return_full_condition": _to_str(row.get("戻入全額条件")),
            "return_half_condition": _to_str(row.get("戻入半額条件")),
            "penalty": _to_float(row.get("違約金")),
        }
    return records
