import { CheckIcon } from 'lucide-react';

import { cn } from '@/lib/utils';

export interface StepperStep {
  label: string;
  description?: string;
}

interface StepperProps {
  steps: StepperStep[];
  /** 0-based current step index. -1 if no step active. */
  current: number;
}

export function Stepper({ steps, current }: StepperProps) {
  return (
    <ol className="flex items-center w-full text-sm">
      {steps.map((step, idx) => {
        const completed = idx < current;
        const active = idx === current;
        return (
          <li
            key={step.label}
            className={cn(
              'flex items-center',
              idx < steps.length - 1 && "after:content-[''] after:w-full after:h-px after:mx-2 after:bg-border"
            )}
          >
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  'flex items-center justify-center w-8 h-8 rounded-full border-2',
                  completed && 'bg-primary border-primary text-primary-foreground',
                  active && 'border-primary text-primary',
                  !completed && !active && 'border-border text-muted-foreground'
                )}
              >
                {completed ? <CheckIcon className="w-4 h-4" /> : <span>{idx + 1}</span>}
              </div>
              <div className="mt-2 text-xs whitespace-nowrap">
                <div className={cn('font-medium', active && 'text-primary')}>{step.label}</div>
                {step.description ? (
                  <div className="text-muted-foreground text-[10px]">{step.description}</div>
                ) : null}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export const COMMISSION_STEPS: StepperStep[] = [
  { label: 'アップロード', description: 'Excel ファイル' },
  { label: 'データパース', description: '正規化' },
  { label: '手数料計算', description: 'マスタ参照' },
  { label: '差異レビュー', description: 'HITL 承認' },
  { label: '確定・エクスポート', description: 'xlsx 出力' },
];
