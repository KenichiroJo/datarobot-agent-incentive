// HITL レビューページ
// バックエンドの /api/v1/commission/results/{sid}?status=hitl_pending を表示し、
// /api/v1/commission/hitl/approve で承認結果を反映する

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, ListChecks } from 'lucide-react';

import { useApproveHitl, useResults } from '@/api/commission/hooks';
import type { AnomalyType } from '@/api/commission/types';
import { HitlBreakdownBar } from '@/components/block/commission/HitlBreakdownBar';
import {
  HitlReviewTable,
  type HitlDecisionMap,
} from '@/components/block/commission/HitlReviewTable';
import { Button } from '@/components/ui/button';
import { PATHS } from '@/constants/path';
import { useCommissionSession } from '@/store/commission-session-store';
import { toast } from 'sonner';

export default function ReviewPage() {
  const navigate = useNavigate();
  const sessionId = useCommissionSession((s) => s.sessionId);
  const { data, isLoading } = useResults(sessionId, { status: 'hitl_pending', per_page: 500 });
  const approve = useApproveHitl();

  const [decisions, setDecisions] = useState<HitlDecisionMap>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const records = data?.records ?? [];
  const total = data?.total ?? 0;

  // 異常理由別件数を集計
  const breakdownCounts = useMemo(() => {
    const c: Record<AnomalyType, number> = { master_not_found: 0, high_amount: 0, calc_error: 0 };
    for (const r of records) {
      const k = (r.hitl_reason ?? 'master_not_found') as AnomalyType;
      c[k] = (c[k] ?? 0) + 1;
    }
    return c;
  }, [records]);

  const approvedCount = Object.values(decisions).filter((d) => d.action === 'approve' || d.action === 'manual').length;
  const rejectedCount = Object.values(decisions).filter((d) => d.action === 'reject').length;
  const remainingCount = records.length - Object.keys(decisions).length;

  const setDecision = (rno: string, d: { action: 'approve' | 'reject' | 'manual'; manualAmount?: number } | null) => {
    setDecisions((prev) => {
      const next = { ...prev };
      if (d === null) {
        delete next[rno];
      } else {
        next[rno] = d;
      }
      return next;
    });
  };

  const bulkAction = (action: 'approve' | 'reject') => {
    const targets = selected.size > 0 ? Array.from(selected) : records.map((r) => String(r.record_no));
    setDecisions((prev) => {
      const next = { ...prev };
      for (const t of targets) {
        next[t] = { action };
      }
      return next;
    });
    toast.success(`${targets.length} 件を${action === 'approve' ? '承認' : '却下'}に設定しました`);
  };

  const approveMasterHitOnly = () => {
    const matched = records.filter((r) => r.master_found);
    setDecisions((prev) => {
      const next = { ...prev };
      for (const r of matched) {
        next[String(r.record_no)] = { action: 'approve' };
      }
      return next;
    });
    toast.success(`マスタヒット ${matched.length} 件を承認に設定`);
  };

  const finalize = async () => {
    if (!sessionId) return;
    const approvals = Object.entries(decisions).map(([rno, d]) => ({
      record_no: Number.isNaN(Number(rno)) ? rno : Number(rno),
      action: d.action,
      manual_amount: d.action === 'manual' ? d.manualAmount ?? null : null,
    }));
    if (approvals.length === 0) {
      toast.warning('決定済みのレコードがありません');
      return;
    }
    try {
      await approve.mutateAsync({ session_id: sessionId, approvals });
      toast.success(`${approvals.length} 件の決定を反映しました`);
      // 残り 0 件なら結果ページへ
      if (remainingCount === 0) {
        navigate(PATHS.COMMISSION.RESULT);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : '承認の反映に失敗しました';
      toast.error(msg);
    }
  };

  return (
    <div className="space-y-6 p-6 pb-32">
      <header>
        <h1 className="text-2xl font-bold text-[var(--commission-text-primary)]">差異レビュー</h1>
        <p className="text-sm text-[var(--commission-text-muted)]">
          異常検知されたレコードを確認し、承認 / 却下 / 手動入力で意思決定してください。
        </p>
      </header>

      <HitlBreakdownBar counts={breakdownCounts} total={total} />

      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" onClick={() => bulkAction('approve')}>
          <ListChecks className="size-3" />
          {selected.size > 0 ? `選択中 ${selected.size} 件を一括承認` : '全件承認'}
        </Button>
        <Button variant="secondary" size="sm" onClick={approveMasterHitOnly}>
          マスタヒットのみ承認
        </Button>
        <Button variant="secondary" size="sm" onClick={() => bulkAction('reject')}>
          {selected.size > 0 ? `選択中 ${selected.size} 件を一括却下` : '全件却下'}
        </Button>
      </div>

      {isLoading ? (
        <div className="rounded-md border bg-card p-6 text-center text-sm text-muted-foreground">
          読み込み中…
        </div>
      ) : (
        <HitlReviewTable
          records={records}
          decisions={decisions}
          selected={selected}
          onSelectionChange={setSelected}
          onDecisionChange={setDecision}
        />
      )}

      {/* フローティング固定パネル */}
      <div className="fixed right-6 bottom-6 w-72 rounded-md border bg-card p-4 shadow-lg">
        <div className="mb-2 text-sm font-semibold">確定パネル</div>
        <ul className="space-y-1 text-xs">
          <li>選択中: {selected.size} 件</li>
          <li className="text-[var(--commission-success)]">
            承認/手動: {approvedCount} 件
          </li>
          <li className="text-[var(--commission-danger)]">却下: {rejectedCount} 件</li>
          <li className="text-muted-foreground">残り: {remainingCount} 件</li>
        </ul>
        <Button
          size="lg"
          className="mt-3 w-full"
          onClick={finalize}
          disabled={approve.isPending || Object.keys(decisions).length === 0}
        >
          {approve.isPending ? '反映中…' : '確定する'}
          <ArrowRight className="ml-1 size-4" />
        </Button>
      </div>
    </div>
  );
}
