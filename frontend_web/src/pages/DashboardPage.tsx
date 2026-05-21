// ダッシュボード: KPI / ステッパー / イベントタイムライン

import { useDashboard } from '@/api/commission/hooks';
import { EventTimeline } from '@/components/block/commission/EventTimeline';
import { KpiCard } from '@/components/block/commission/KpiCard';
import { ProcessStepper } from '@/components/block/commission/ProcessStepper';
import { useCommissionSession } from '@/store/commission-session-store';

function formatYen(n: number): string {
  return `¥${n.toLocaleString('ja-JP')}`;
}

function formatPercent(p: number): string {
  return `${(p * 100).toFixed(1)}%`;
}

export default function DashboardPage() {
  const sessionId = useCommissionSession((s) => s.sessionId);
  const { data, isLoading } = useDashboard(sessionId, Boolean(sessionId));

  const kpi = data?.kpi;
  const events = data?.events ?? [];
  const phases = data?.processing_phases ?? {};

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-bold text-[var(--commission-text-primary)]">ダッシュボード</h1>
        <p className="text-sm text-[var(--commission-text-muted)]">
          {sessionId
            ? `セッション ${sessionId.slice(0, 14)}… の処理状況`
            : 'ファイルアップロードからワークフローを開始してください。'}
        </p>
      </header>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="総処理件数"
          value={kpi?.total_records ?? 0}
          suffix="件"
          accent="primary"
          hint={isLoading ? '読み込み中…' : undefined}
        />
        <KpiCard
          label="自動完了率"
          value={kpi ? formatPercent(kpi.auto_completion_rate) : '0.0%'}
          accent="success"
          hint={kpi ? `${kpi.auto_completed} 件自動完了` : undefined}
        />
        <KpiCard
          label="HITL 承認待ち"
          value={kpi?.hitl_pending ?? 0}
          suffix="件"
          accent="warning"
          hint={kpi?.hitl_approved ? `${kpi.hitl_approved} 件承認済み` : undefined}
        />
        <KpiCard
          label="手数料合計額"
          value={formatYen(kpi?.total_commission_amount ?? 0)}
          accent="navy"
        />
      </section>

      <section className="rounded-md border bg-card p-6">
        <h2 className="mb-4 text-sm font-semibold text-[var(--commission-text-primary)]">処理フェーズ</h2>
        <ProcessStepper phases={phases} />
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-[var(--commission-text-primary)]">最新イベント</h2>
        <EventTimeline events={events} />
      </section>
    </div>
  );
}
