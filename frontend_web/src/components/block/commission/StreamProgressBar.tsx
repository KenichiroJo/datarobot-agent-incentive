// シンプルな進捗バー (shadcn Progress 未インストールでも動くよう CSS のみで実装)

interface StreamProgressBarProps {
  current: number;
  total: number;
  label?: string;
}

export function StreamProgressBar({ current, total, label }: StreamProgressBarProps) {
  const pct = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium">{label ?? '進捗'}</span>
        <span className="font-mono text-[var(--commission-text-muted)]">
          {current.toLocaleString()} / {total.toLocaleString()} 件 ({pct}%)
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded bg-muted">
        <div
          className="h-full bg-[var(--commission-accent)] transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
