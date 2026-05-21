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
"""コミッション計算 API の Pydantic schema 群。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ===============================================================
# Upload
# ===============================================================


class UploadedFileInfo(BaseModel):
    file_id: str
    filename: str
    size: int
    detected_type: Literal["sales", "master", "unknown"]


class UploadResponse(BaseModel):
    session_id: str
    uploaded: list[UploadedFileInfo]
    message: str


# ===============================================================
# Calculate
# ===============================================================


class CalculateOptions(BaseModel):
    anomaly_threshold: int = Field(default=100_000, ge=0)
    auto_approve_clean: bool = True


class CalculateRequest(BaseModel):
    session_id: str
    file_ids: list[str] = Field(default_factory=list)
    options: CalculateOptions = Field(default_factory=CalculateOptions)


# ===============================================================
# Results / Records
# ===============================================================


class ResultRecord(BaseModel):
    record_no: int | str | None = None
    取引先コード: int | str | None = Field(default=None, alias="partner_code")
    取引先名称: str | None = Field(default=None, alias="partner_name")
    商材: str | None = Field(default=None, alias="product")
    決済方法: str | None = Field(default=None, alias="payment_method")
    total_commission: int = 0
    basic_commission: int = 0
    volume_incentive: int = 0
    special_commission_1: int = 0
    special_commission_2: int = 0
    continuous_commission: int = 0
    referral_commission: int = 0
    pap_commission: int = 0
    pas_commission: int = 0
    ph_commission: int = 0
    qi_amount: int = 0
    debit_initial_fee: int = 0
    return_amount: int = 0
    master_found: bool = False
    is_anomaly: bool = False
    status: str = "unknown"
    hitl_reason: str | None = None
    hitl_reason_ja: str | None = None
    master_key_used: str | None = None
    calculation_trace: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class ResultsResponse(BaseModel):
    session_id: str
    records: list[ResultRecord]
    total: int
    page: int
    per_page: int
    summary: dict[str, Any] | None = None


# ===============================================================
# HITL
# ===============================================================


class HITLApproval(BaseModel):
    record_no: int | str
    action: Literal["approve", "reject", "manual"]
    manual_amount: int | None = None


class HITLApproveRequest(BaseModel):
    session_id: str
    approvals: list[HITLApproval]


class HITLApproveResponse(BaseModel):
    approved_count: int
    rejected_count: int
    manual_count: int
    remaining_hitl: int


# ===============================================================
# Dashboard
# ===============================================================


class DashboardKpi(BaseModel):
    total_records: int = 0
    auto_completed: int = 0
    hitl_pending: int = 0
    hitl_approved: int = 0
    error_count: int = 0
    total_commission_amount: int = 0
    auto_completion_rate: float = 0.0


class PartnerAggregate(BaseModel):
    partner: str
    record_count: int
    total_commission: int


class ProductAggregate(BaseModel):
    product: str
    record_count: int
    total_commission: int


class DashboardEventItem(BaseModel):
    id: str
    kind: str
    message: str
    meta: dict[str, Any] = Field(default_factory=dict)
    ts: float


class DashboardResponse(BaseModel):
    session_id: str
    kpi: DashboardKpi
    by_partner: list[PartnerAggregate] = Field(default_factory=list)
    by_product: list[ProductAggregate] = Field(default_factory=list)
    by_status: dict[str, int] = Field(default_factory=dict)
    processing_phases: dict[str, str] = Field(default_factory=dict)
    events: list[DashboardEventItem] = Field(default_factory=list)
