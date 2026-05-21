import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { approveHitl, fetchDashboard, fetchResults, uploadFiles } from './api-requests';
import type { HitlDecision } from './types';

export function useUploadFiles() {
  return useMutation({
    mutationFn: (files: File[]) => uploadFiles(files),
  });
}

export function useResults(
  sessionId: string | undefined,
  options: { status?: string; page?: number; perPage?: number } = {}
) {
  return useQuery({
    queryKey: ['commission', 'results', sessionId, options.status, options.page, options.perPage],
    queryFn: () => fetchResults(sessionId as string, options),
    enabled: !!sessionId,
  });
}

export function useDashboard(sessionId: string | undefined) {
  return useQuery({
    queryKey: ['commission', 'dashboard', sessionId],
    queryFn: () => fetchDashboard(sessionId as string),
    enabled: !!sessionId,
  });
}

export function useApproveHitl(sessionId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (approvals: HitlDecision[]) => approveHitl(sessionId as string, approvals),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['commission', 'results', sessionId] });
      qc.invalidateQueries({ queryKey: ['commission', 'dashboard', sessionId] });
    },
  });
}
