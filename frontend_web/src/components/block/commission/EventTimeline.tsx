// 最新 10 件のシステムイベントを時系列で表示

import type { DashboardEventItem } from '@/api/commission/types';

interface EventTimelineProps {
  events: DashboardEventItem[];
}

const KIND_DOT: Record<string, string> = {
  session_created: 'bg-[var(--commission-accent)]',
  upload: 'bg-[var(--commission-primary)]',
  calculate_start: 'bg-[var(--commission-accent)]',
  calculate_done: 'bg-[var(--commission-success)]',
  hitl_decisions: 'bg-[var(--commission-warning)]',
};

function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleString('ja-JP', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function EventTimeline({ events }: EventTimelineProps) {
  if (!events.length) {
    return (
      <div className="rounded-md border border-dashed bg-card p-6 text-center text-sm text-muted-foreground">
        まだイベントはありません。ファイルをアップロードして処理を開始してください。
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {events
        .slice()
        .reverse()
        .map((e) => (
          <div
            key={e.id}
            className="flex items-start gap-3 rounded-md border bg-card p-3 text-sm"
          >
            <div
              className={`mt-1.5 size-2 shrink-0 rounded-full ${KIND_DOT[e.kind] ?? 'bg-muted-foreground'}`}
            />
            <div className="flex-1">
              <div className="text-foreground">{e.message}</div>
              <div className="text-xs text-muted-foreground">
                {formatTime(e.ts)} · {e.kind}
              </div>
            </div>
          </div>
        ))}
    </div>
  );
}
