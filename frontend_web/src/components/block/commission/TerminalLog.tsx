// SSE ログを黒背景 / 等幅で append-only に表示するターミナル風 UI

import { useEffect, useRef } from 'react';

interface LogEntry {
  ts: number;
  level: 'info' | 'warn' | 'error';
  message: string;
}

interface TerminalLogProps {
  entries: LogEntry[];
  height?: string;
}

const LEVEL_COLOR: Record<LogEntry['level'], string> = {
  info: 'text-emerald-300',
  warn: 'text-amber-300',
  error: 'text-rose-300',
};

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString('ja-JP', { hour12: false });
}

export function TerminalLog({ entries, height = 'h-72' }: TerminalLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries.length]);

  return (
    <div
      ref={scrollRef}
      className={`overflow-auto rounded-md bg-black px-4 py-3 font-mono text-xs leading-relaxed text-emerald-100 ${height}`}
    >
      {entries.length === 0 ? (
        <div className="text-muted-foreground">
          {'> '}
          ストリームを待機しています…
        </div>
      ) : (
        entries.map((e, i) => (
          <div key={i} className="flex gap-3">
            <span className="text-zinc-500">[{formatTime(e.ts)}]</span>
            <span className={LEVEL_COLOR[e.level]}>{e.message}</span>
          </div>
        ))
      )}
    </div>
  );
}
