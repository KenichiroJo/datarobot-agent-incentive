// コミッション計算 API の TypeScript 型定義

export type DetectedFileType = 'sales' | 'master' | 'unknown';

export type ProcessingStatus =
  | 'idle'
  | 'uploading'
  | 'parsing'
  | 'calculating'
  | 'awaiting_hitl'
  | 'approving'
  | 'explaining'
  | 'done'
  | 'error';

export type AnomalyType = 'master_not_found' | 'high_amount' | 'calc_error';

export type RecordStatus =
  | 'ok'
  | 'master_not_found'
  | 'high_amount'
  | 'calc_error'
  | 'hitl_approved'
  | 'hitl_rejected'
  | 'manual'
  | 'unknown';

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

export interface CalculateOptions {
  anomaly_threshold: number;
  auto_approve_clean: boolean;
}

export interface CalculateRequest {
  session_id: string;
  file_ids?: string[];
  options?: Partial<CalculateOptions>;
}

export interface ResultRecord {
  record_no: number | string | null;
  partner_code: number | string | null;
  partner_name: string | null;
  product: string | null;
  payment_method: string | null;
  total_commission: number;
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
  master_found: boolean;
  is_anomaly: boolean;
  status: RecordStatus;
  hitl_reason: AnomalyType | null;
  hitl_reason_ja: string | null;
  master_key_used: string | null;
  calculation_trace: string[];
}

export interface ResultsResponse {
  session_id: string;
  records: ResultRecord[];
  total: number;
  page: number;
  per_page: number;
  summary?: SummaryData;
}

export interface HITLApproval {
  record_no: number | string;
  action: 'approve' | 'reject' | 'manual';
  manual_amount?: number | null;
}

export interface HITLApproveRequest {
  session_id: string;
  approvals: HITLApproval[];
}

export interface HITLApproveResponse {
  approved_count: number;
  rejected_count: number;
  manual_count: number;
  remaining_hitl: number;
}

export interface DashboardKpi {
  total_records: number;
  auto_completed: number;
  hitl_pending: number;
  hitl_approved: number;
  error_count: number;
  total_commission_amount: number;
  auto_completion_rate: number;
}

export interface PartnerAggregate {
  partner: string;
  record_count: number;
  total_commission: number;
}

export interface ProductAggregate {
  product: string;
  record_count: number;
  total_commission: number;
}

export interface SummaryData {
  kpi: DashboardKpi;
  by_partner: PartnerAggregate[];
  by_product: ProductAggregate[];
  by_status: Record<string, number>;
}

export interface DashboardEventItem {
  id: string;
  kind: string;
  message: string;
  meta: Record<string, unknown>;
  ts: number;
}

export interface DashboardResponse {
  session_id: string;
  kpi: DashboardKpi;
  by_partner: PartnerAggregate[];
  by_product: ProductAggregate[];
  by_status: Record<string, number>;
  processing_phases: Record<string, string>;
  events: DashboardEventItem[];
}

// SSE イベント (POST /calculate)
export type CalculationStreamEvent =
  | { type: 'status'; node?: string; status?: string; message?: string; pending_count?: number }
  | { type: 'progress'; current: number; total: number }
  | { type: 'result'; data?: { summary?: SummaryData; anomaly_count?: number; hitl_required?: boolean }; delta?: string }
  | { type: 'error'; message: string }
  | { type: 'done'; reason?: string };
