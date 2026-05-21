// コミッション計算 API クライアント (axios 経由)
//
// 重要: apiClient の baseURL は既に `/api` を含むため、ここでは `/v1/commission/...` を渡す
// (`/api/v1/commission/...` を渡すと baseURL と二重になり 404 になる)

import apiClient from '@/api/apiClient';
import type {
  DashboardResponse,
  HITLApproveRequest,
  HITLApproveResponse,
  ResultsResponse,
  UploadResponse,
} from './types';

const BASE = '/v1/commission';

export async function uploadFiles(payload: {
  files: File[];
  sessionId?: string;
}): Promise<UploadResponse> {
  const form = new FormData();
  for (const f of payload.files) {
    form.append('files', f);
  }
  if (payload.sessionId) {
    form.append('session_id', payload.sessionId);
  }
  const { data } = await apiClient.post<UploadResponse>(`${BASE}/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function getResults(
  sessionId: string,
  params: { status?: string; page?: number; per_page?: number } = {},
): Promise<ResultsResponse> {
  const { data } = await apiClient.get<ResultsResponse>(`${BASE}/results/${sessionId}`, {
    params,
  });
  return data;
}

export async function approveHitl(payload: HITLApproveRequest): Promise<HITLApproveResponse> {
  const { data } = await apiClient.post<HITLApproveResponse>(`${BASE}/hitl/approve`, payload);
  return data;
}

export async function getDashboard(sessionId: string): Promise<DashboardResponse> {
  const { data } = await apiClient.get<DashboardResponse>(`${BASE}/dashboard/${sessionId}`);
  return data;
}

export async function exportCsv(sessionId: string): Promise<Blob> {
  const response = await apiClient.get<Blob>(`${BASE}/export/${sessionId}`, {
    responseType: 'blob',
  });
  return response.data;
}

export async function resetSession(sessionId: string): Promise<{ status: string; session_id: string }> {
  const form = new FormData();
  form.append('session_id', sessionId);
  const { data } = await apiClient.post<{ status: string; session_id: string }>(
    `${BASE}/session/reset`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}
