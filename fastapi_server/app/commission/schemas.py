"""手数料計算 API のリクエスト/レスポンス Pydantic モデル。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class UploadedFileInfo(BaseModel):
    file_id: str
    filename: str
    size: int
    detected_type: Literal["sales", "master", "unknown"]


class UploadResponse(BaseModel):
    session_id: str
    uploaded: list[UploadedFileInfo]
    message: str


class CalculateOptions(BaseModel):
    anomaly_threshold: int = 100_000
    auto_approve_clean: bool = True


class CalculateRequest(BaseModel):
    options: CalculateOptions = Field(default_factory=CalculateOptions)


class HitlDecisionItem(BaseModel):
    record_no: int
    action: Literal["approve", "reject", "manual"]
    manual_amount: float | None = None
    note: str | None = None


class HitlApproveRequest(BaseModel):
    approvals: list[HitlDecisionItem]


class HitlApproveResponse(BaseModel):
    approved_count: int
    rejected_count: int
    manual_count: int
    remaining_hitl: int


class ResultRecord(BaseModel):
    record_no: int
    partner_code: int
    partner_name: str | None = None
    product: str
    payment_method: str
    total_commission: int
    is_anomaly: bool
    hitl_reason: str | None = None
    master_found: bool
    master_key_used: str


class ResultsResponse(BaseModel):
    results: list[dict]
    total: int
    page: int
    per_page: int
    summary: dict | None = None


class DashboardKPI(BaseModel):
    total_records: int
    auto_completed: int
    hitl_pending: int
    hitl_approved: int
    error_count: int
    total_commission_amount: int
    auto_completion_rate: float


class DashboardResponse(BaseModel):
    kpi: DashboardKPI
    by_partner: list[dict]
    by_product: list[dict]
    processing_status: str
