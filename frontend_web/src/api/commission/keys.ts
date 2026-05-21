// TanStack React Query キー定義

export const commissionKeys = {
  all: ['commission'] as const,
  dashboard: (sessionId: string) => [...commissionKeys.all, 'dashboard', sessionId] as const,
  results: (sessionId: string, params?: Record<string, string | number | undefined>) =>
    [...commissionKeys.all, 'results', sessionId, params ?? {}] as const,
} as const;
