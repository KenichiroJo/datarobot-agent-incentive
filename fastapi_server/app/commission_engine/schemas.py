"""手数料計算で使う Pydantic モデル。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SalesRecord(BaseModel):
    """売上明細 1 行分の正規化データ。"""

    record_no: int = Field(description="レコードNo（手数料明細用）")
    file_kbn: str = Field(description="ファイル区分")
    contract_id: int = Field(description="契約ID")
    application_date: datetime = Field(description="申込日付")
    application_month: datetime = Field(description="申込月 (YYYY-MM-01)")
    shipping_date: datetime | None = Field(default=None, description="出荷日")
    product_category: str = Field(description="商材カテゴリ (例: サーバー)")
    product_name: str = Field(description="（Rename）商材 — プラン名")
    payment_method_raw: str = Field(description="出荷時決済方法 — 原データ")
    payment_method: str = Field(description="（Rename）決済方法 — 統一名")
    acquirer_id: int = Field(description="獲得者ID")
    partner_code: int = Field(description="（Rename）取引先コード — 10 桁")
    cs_id: int | None = Field(default=None, description="CSID")
    acquirer_name: str | None = Field(default=None, description="獲得者名")
    acquirer_shop_name: str | None = Field(default=None, description="獲得店舗名")
    delivery_count: int = Field(description="配送個数")
    customer_price: int = Field(description="販売価格_顧客")
    lookup_key: str = Field(description="マスタ参照用複合キー")
    raw: dict = Field(default_factory=dict, description="その他原データ（生）")


class MasterRecord(BaseModel):
    """取引条件マスタ 1 行分。"""

    key: str = Field(description="複合キー")
    partner_name: str = Field(description="取引先名称")
    primary_partner_code: int = Field(description="一次店コード")
    commission_kbn: str | None = Field(default=None, description="コミッション区分")
    condition_definition: str | None = Field(default=None, description="条件適用定義")
    payment_definition: str | None = Field(default=None, description="支払定義")
    product: str = Field(description="商材 — プラン名")
    payment_method: str = Field(description="決済方法")
    basic_commission: float = Field(default=0, description="基本コミッション")
    volume_incentive: float = Field(default=0, description="ボリュームインセンティブ")
    special_commission_1: float = Field(default=0, description="特別コミッション")
    special_commission_2: float = Field(default=0, description="特別コミッション②")
    qi_scope: float | None = Field(default=None, description="QI適用範囲")
    qi_split_period: float | None = Field(default=None, description="QI分割計上期間")
    debit_initial_fee: float = Field(default=0, description="口振分割時初回手数料")
    referral_kbn: float | None = Field(default=None, description="紹介制度区分")
    referral_commission: float = Field(default=0, description="紹介制度コミッション")
    continuous_flag_25_37: float | None = Field(
        default=None, description="25・37ヶ月目以降継続コミッションフラグ"
    )
    continuous_commission: float = Field(default=0, description="継続コミッション")
    pap_kbn: str | None = Field(default=None, description="PAP区分")
    pap_commission: float = Field(default=0, description="PAPコミッション")
    pas_kbn: str | None = Field(default=None, description="PAS区分")
    pas_commission: float = Field(default=0, description="PASコミッション")
    ph_kbn: str | None = Field(default=None, description="PH区分（6L/デリキチ等）")
    ph_commission: float = Field(default=0, description="PHコミッション")
    return_condition: str | None = Field(default=None, description="戻入条件")
    return_full_condition: str | None = Field(
        default=None, description="戻入全額条件 (例: 12本未満)"
    )
    return_half_condition: str | None = Field(
        default=None, description="戻入半額条件 (例: 24本未満)"
    )
    penalty: float = Field(default=0, description="違約金")
    raw: dict = Field(default_factory=dict, description="その他原データ")


class CommissionResult(BaseModel):
    """1 レコードの手数料計算結果。"""

    record_no: int
    partner_code: int
    partner_name: str | None = None
    product: str
    payment_method: str
    basic_commission: float = 0
    volume_incentive: float = 0
    special_commission_1: float = 0
    special_commission_2: float = 0
    continuous_commission: float = 0
    referral_commission: float = 0
    pap_commission: float = 0
    pas_commission: float = 0
    ph_commission: float = 0
    qi_amount: float = 0
    debit_initial_fee: float = 0
    return_amount: float = 0
    total_commission: float = 0
    master_key_used: str
    calculation_trace: list[str] = Field(default_factory=list)
    master_found: bool = True
    is_anomaly: bool = False
    hitl_reason: str | None = None
    error_message: str | None = None


class HitlDecision(BaseModel):
    """HITL ノードへの再開入力。"""

    record_no: int
    action: Literal["approve", "reject", "manual"]
    manual_amount: float | None = None
    note: str | None = None


class SummaryReport(BaseModel):
    """全体サマリ。"""

    total_records: int
    auto_completed: int
    hitl_pending: int
    error_count: int
    total_commission_amount: float
    auto_completion_rate: float
    by_partner: list[dict] = Field(default_factory=list)
    by_product: list[dict] = Field(default_factory=list)
