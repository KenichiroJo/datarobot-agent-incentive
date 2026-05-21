// React Query hooks for commission API

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  approveHitl,
  exportCsv,
  getDashboard,
  getResults,
  resetSession,
  uploadFiles,
} from './api-requests';
import { commissionKeys } from './keys';

export function useDashboard(sessionId: string | null, enabled = true) {
  return useQuery({
    queryKey: commissionKeys.dashboard(sessionId ?? '__none__'),
    queryFn: () => getDashboard(sessionId as string),
    enabled: enabled && Boolean(sessionId),
    refetchInterval: 3000,
  });
}

export function useResults(
  sessionId: string | null,
  params: { status?: string; page?: number; per_page?: number } = {},
  enabled = true,
) {
  return useQuery({
    queryKey: commissionKeys.results(sessionId ?? '__none__', params),
    queryFn: () => getResults(sessionId as string, params),
    enabled: enabled && Boolean(sessionId),
  });
}

export function useUploadFiles() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: uploadFiles,
    onSuccess: (_, variables) => {
      if (variables.sessionId) {
        qc.invalidateQueries({ queryKey: commissionKeys.dashboard(variables.sessionId) });
      }
    },
  });
}

export function useApproveHitl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: approveHitl,
    onSuccess: (_, variables) => {
      qc.invalidateQueries({ queryKey: commissionKeys.dashboard(variables.session_id) });
      qc.invalidateQueries({ queryKey: ['commission', 'results', variables.session_id] });
    },
  });
}

export function useResetSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: resetSession,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: commissionKeys.all });
    },
  });
}

export function useExportCsv() {
  return useMutation({
    mutationFn: async (sessionId: string) => {
      const blob = await exportCsv(sessionId);
      // ブラウザでダウンロードをトリガー
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `commission_${sessionId}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      return blob;
    },
  });
}
