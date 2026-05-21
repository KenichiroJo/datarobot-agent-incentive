// 単一の KPI を表示するカードコンポーネント

import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface KpiCardProps {
  label: string;
  value: string | number;
  suffix?: string;
  accent?: 'primary' | 'success' | 'warning' | 'navy';
  hint?: string;
}

const ACCENT_CLASSES: Record<NonNullable<KpiCardProps['accent']>, string> = {
  primary: 'border-l-[var(--commission-accent)]',
  success: 'border-l-[var(--commission-success)]',
  warning: 'border-l-[var(--commission-warning)]',
  navy: 'border-l-[var(--commission-primary)]',
};

export function KpiCard({ label, value, suffix, accent = 'primary', hint }: KpiCardProps) {
  return (
    <Card className={cn('flex flex-col gap-1 border-l-4 px-4 py-3', ACCENT_CLASSES[accent])}>
      <div className="text-xs font-medium text-[var(--commission-text-muted)]">{label}</div>
      <div className="text-2xl font-bold text-[var(--commission-text-primary)]">
        {value}
        {suffix ? <span className="ml-1 text-sm font-normal">{suffix}</span> : null}
      </div>
      {hint ? <div className="text-xs text-muted-foreground">{hint}</div> : null}
    </Card>
  );
}
