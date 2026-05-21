import apiClient from '@/api/apiClient';

import type {
  DashboardResponse,
  HitlApproveResponse,
  HitlDecision,
  ResultsResponse,
  UploadResponse,
} from './types';

export async function uploadFiles(files: File[]): Promise<UploadResponse> {
  const fd = new FormData();
  for (const f of files) {
    fd.append('files', f);
  }
  const res = await apiClient.post<UploadResponse>('/v1/commission/upload', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function fetchResults(
  sessionId: string,
  options: { status?: string; page?: number; perPage?: number } = {}
): Promise<ResultsResponse> {
  const res = await apiClient.get<ResultsResponse>(`/v1/commission/results/${sessionId}`, {
    params: {
      status_filter: options.status ?? 'all',
      page: options.page ?? 1,
      per_page: options.perPage ?? 50,
    },
  });
  return res.data;
}

export async function approveHitl(
  sessionId: string,
  approvals: HitlDecision[]
): Promise<HitlApproveResponse> {
  const res = await apiClient.post<HitlApproveResponse>(
    `/v1/commission/hitl/approve/${sessionId}`,
    { approvals }
  );
  return res.data;
}

export async function fetchDashboard(sessionId: string): Promise<DashboardResponse> {
  const res = await apiClient.get<DashboardResponse>(`/v1/commission/dashboard/${sessionId}`);
  return res.data;
}

export function getExportUrl(sessionId: string): string {
  // baseURL を含めた絶対 URL を返す
  const base = apiClient.defaults.baseURL ?? '';
  return `${base}/v1/commission/export/${sessionId}`;
}

/**
 * SSE で /calculate を呼ぶ。AbortController で接続管理。
 * onEvent には (eventName, data) が渡る。
 */
export async function streamCalculate(
  sessionId: string,
  options: { signal?: AbortSignal; onEvent: (event: string, data: unknown) => void }
): Promise<void> {
  const base = apiClient.defaults.baseURL ?? '';
  const url = `${base}/v1/commission/calculate/${sessionId}`;
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'text/event-stream', 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
    signal: options.signal,
  });
  if (!res.body) {
    throw new Error('No response body for SSE');
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    // SSE: separate events by \n\n
    while (true) {
      const idx = buf.indexOf('\n\n');
      if (idx < 0) break;
      const raw = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let eventName = 'message';
      let dataLine = '';
      for (const line of raw.split('\n')) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        if (line.startsWith('data:')) dataLine += line.slice(5).trim();
      }
      let parsed: unknown = dataLine;
      try {
        parsed = JSON.parse(dataLine);
      } catch {
        // keep raw string
      }
      options.onEvent(eventName, parsed);
    }
  }
}
