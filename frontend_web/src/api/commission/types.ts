export type DetectedFileType = 'sales' | 'master' | 'unknown';

export interface UploadedFileInfo {
  file_id: string;
  filename: string;
  size: number;
  detected_type: DetectedFileType;
}

export interface UploadResponse {
  session_id: string;
  uploaded: UploadedFileInfo[];
  message: string;
}

export interface CommissionResult {
  record_no: number;
  partner_code: number;
  partner_name: string | null;
  product: string;
  payment_method: string;
  basic_commission: number;
  volume_incentive: number;
  special_commission_1: number;
  special_commission_2: number;
  continuous_commission: number;
  referral_commission: number;
  pap_commission: number;
  pas_commission: number;
  ph_commission: number;
  qi_amount: number;
  debit_initial_fee: number;
  return_amount: number;
  total_commission: number;
  master_key_used: string;
  calculation_trace: string[];
  master_found: boolean;
  is_anomaly: boolean;
  hitl_reason: string | null;
  error_message: string | null;
}

export interface PartnerTotal {
  name: string;
  count: number;
  total: number;
}

export interface SummaryReport {
  total_records: number;
  auto_completed: number;
  hitl_pending: number;
  error_count: number;
  total_commission_amount: number;
  auto_completion_rate: number;
  by_partner: PartnerTotal[];
  by_product: PartnerTotal[];
}

export interface ResultsResponse {
  results: CommissionResult[];
  total: number;
  page: number;
  per_page: number;
  summary: SummaryReport | null;
}

export interface DashboardKPI {
  total_records: number;
  auto_completed: number;
  hitl_pending: number;
  hitl_approved: number;
  error_count: number;
  total_commission_amount: number;
  auto_completion_rate: number;
}

export interface DashboardResponse {
  kpi: DashboardKPI;
  by_partner: PartnerTotal[];
  by_product: PartnerTotal[];
  processing_status: string;
}

export type HitlAction = 'approve' | 'reject' | 'manual';

export interface HitlDecision {
  record_no: number;
  action: HitlAction;
  manual_amount?: number;
  note?: string;
}

export interface HitlApproveResponse {
  approved_count: number;
  rejected_count: number;
  manual_count: number;
  remaining_hitl: number;
}

export type SseEventType = 'progress' | 'status' | 'hitl_required' | 'result' | 'error' | 'done';

export interface SseEvent {
  type: SseEventType;
  data: Record<string, unknown>;
}
