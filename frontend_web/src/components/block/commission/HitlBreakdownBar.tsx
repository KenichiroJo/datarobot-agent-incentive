// 異常理由別件数を積み上げ式バーで可視化

import type { AnomalyType } from '@/api/commission/types';

interface BreakdownBarProps {
  counts: Record<AnomalyType, number>;
  total: number;
}

const SEGMENT_STYLE: Record<AnomalyType, { color: string; label: string }> = {
  master_not_found: { color: 'bg-[var(--commission-danger)]', label: 'マスタ未ヒット' },
  high_amount: { color: 'bg-[var(--commission-warning)]', label: '高額アラート' },
  calc_error: { color: 'bg-orange-500', label: '計算エラー' },
};

export function HitlBreakdownBar({ counts, total }: BreakdownBarProps) {
  if (total === 0) {
    return (
      <div className="rounded-md border bg-card p-4 text-sm text-muted-foreground">
        HITL 対象レコードはありません。
      </div>
    );
  }
  const order: AnomalyType[] = ['master_not_found', 'high_amount', 'calc_error'];
  return (
    <div className="space-y-2">
      <div className="text-sm font-semibold">
        HITL 対象: <span className="text-[var(--commission-warning)]">{total.toLocaleString()} 件</span>
      </div>
      <div className="flex h-4 w-full overflow-hidden rounded bg-muted">
        {order.map((kind) => {
          const c = counts[kind] || 0;
          if (c === 0) return null;
          const pct = (c / total) * 100;
          return (
            <div
              key={kind}
              className={SEGMENT_STYLE[kind].color}
              style={{ width: `${pct}%` }}
              title={`${SEGMENT_STYLE[kind].label}: ${c} 件 (${pct.toFixed(1)}%)`}
            />
          );
        })}
      </div>
      <div className="flex flex-wrap gap-4 text-xs">
        {order.map((kind) => (
          <div key={kind} className="flex items-center gap-2">
            <span className={`size-2.5 rounded-sm ${SEGMENT_STYLE[kind].color}`} />
            <span>
              {SEGMENT_STYLE[kind].label}: {(counts[kind] || 0).toLocaleString()} 件
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
