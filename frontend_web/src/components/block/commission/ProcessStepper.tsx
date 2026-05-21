// 5 ステップの処理フェーズステッパー
// ① ファイルアップロード → ② データパース → ③ 手数料計算 → ④ 差異レビュー → ⑤ 確定・エクスポート

import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

export type PhaseStatus = 'pending' | 'in_progress' | 'completed';

interface ProcessStepperProps {
  phases: Record<string, PhaseStatus | string>;
}

const STEP_DEFS = [
  { key: 'upload', label: 'ファイルアップロード' },
  { key: 'parse', label: 'データパース' },
  { key: 'calculate', label: '手数料計算' },
  { key: 'review', label: '差異レビュー' },
  { key: 'finalize', label: '確定・エクスポート' },
] as const;

const STATUS_STYLE: Record<PhaseStatus, { dot: string; text: string }> = {
  pending: {
    dot: 'bg-muted text-muted-foreground border-muted-foreground/40',
    text: 'text-muted-foreground',
  },
  in_progress: {
    dot: 'bg-[var(--commission-accent)] text-white border-[var(--commission-accent)] animate-pulse',
    text: 'text-[var(--commission-accent)] font-semibold',
  },
  completed: {
    dot: 'bg-[var(--commission-success)] text-white border-[var(--commission-success)]',
    text: 'text-[var(--commission-success)] font-semibold',
  },
};

function normalizeStatus(value: string | undefined): PhaseStatus {
  if (value === 'completed' || value === 'in_progress' || value === 'pending') return value;
  return 'pending';
}

export function ProcessStepper({ phases }: ProcessStepperProps) {
  return (
    <div className="flex w-full items-center">
      {STEP_DEFS.map((step, idx) => {
        const status = normalizeStatus(phases[step.key] as string | undefined);
        const style = STATUS_STYLE[status];
        return (
          <div key={step.key} className="flex flex-1 items-center">
            <div className="flex flex-col items-center gap-1">
              <div
                className={cn(
                  'flex size-8 items-center justify-center rounded-full border-2 text-sm font-bold transition-colors',
                  style.dot,
                )}
              >
                {status === 'completed' ? <Check className="size-4" /> : idx + 1}
              </div>
              <div className={cn('text-xs whitespace-nowrap', style.text)}>{step.label}</div>
            </div>
            {idx < STEP_DEFS.length - 1 ? (
              <div
                className={cn(
                  'mx-2 mb-5 h-0.5 flex-1',
                  status === 'completed'
                    ? 'bg-[var(--commission-success)]'
                    : 'bg-muted-foreground/30',
                )}
              />
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
