import { useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';

import { useApproveHitl, useResults } from '@/api/commission/hooks';
import { AnomalyTable } from '@/components/commission/AnomalyTable';
import { FloatingApprovePanel } from '@/components/commission/FloatingApprovePanel';
import { COMMISSION_STEPS, Stepper } from '@/components/commission/Stepper';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PATHS } from '@/constants/path';
import { useCommissionStore } from '@/stores/commissionStore';

import type { HitlDecision } from '@/api/commission/types';

export function ReviewPage() {
  const { sessionId = '' } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { data, isLoading } = useResults(sessionId, { status: 'hitl_pending', perPage: 500 });
  const decisions = useCommissionStore((s) => s.decisions);
  const selected = useCommissionStore((s) => s.selectedRecords);
  const setDecision = useCommissionStore((s) => s.setDecision);
  const clearDecisions = useCommissionStore((s) => s.clearDecisions);
  const deselectAll = useCommissionStore((s) => s.deselectAll);
  const approveMut = useApproveHitl(sessionId);

  const rows = data?.results ?? [];
  const decidedCount = useMemo(() => Object.keys(decisions).length, [decisions]);

  const reasonCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const r of rows) {
      const key = r.master_found ? 'high' : 'master_miss';
      counts[key] = (counts[key] ?? 0) + 1;
    }
    return counts;
  }, [rows]);

  const onApproveAll = () => {
    for (const r of rows) {
      setDecision(r.record_no, { action: 'approve' });
    }
    toast.info(`${rows.length} 件を一括「承認」に設定`);
  };

  const onConfirm = async () => {
    const approvals: HitlDecision[] = Object.entries(decisions).map(([recordNo, dec]) => ({
      record_no: Number(recordNo),
      action: dec.action,
      manual_amount: dec.manual_amount,
      note: dec.note,
    }));
    if (approvals.length === 0) {
      toast.error('決定済みのレコードがありません');
      return;
    }
    try {
      const res = await approveMut.mutateAsync(approvals);
      toast.success(
        `${res.approved_count} 承認 / ${res.rejected_count} 却下 / ${res.manual_count} 手動入力 で確定`
      );
      clearDecisions();
      deselectAll();
      navigate(PATHS.COMMISSION.RESULT.replace(':sessionId', sessionId));
    } catch (e) {
      toast.error('承認失敗: ' + (e instanceof Error ? e.message : String(e)));
    }
  };

  return (
    <div className="container mx-auto p-6 max-w-7xl space-y-6 pb-32">
      <div>
        <h1 className="text-2xl font-bold">差異レビュー (HITL)</h1>
        <p className="text-sm text-muted-foreground mt-1">
          異常検知された手数料計算結果を確認し、承認・却下・手動入力を行ってください
        </p>
      </div>

      <Card>
        <CardContent className="overflow-x-auto py-4">
          <Stepper steps={COMMISSION_STEPS} current={3} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            異常レコード {rows.length} 件
            {reasonCounts.master_miss ? (
              <span className="ml-3 text-xs text-red-600">
                マスタ未ヒット: {reasonCounts.master_miss}
              </span>
            ) : null}
            {reasonCounts.high ? (
              <span className="ml-3 text-xs text-yellow-600">
                高額アラート: {reasonCounts.high}
              </span>
            ) : null}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="p-6 text-center text-muted-foreground">読み込み中...</div>
          ) : (
            <AnomalyTable rows={rows} />
          )}
        </CardContent>
      </Card>

      <FloatingApprovePanel
        selectedCount={selected.length}
        decidedCount={decidedCount}
        totalCount={rows.length}
        onApproveAll={onApproveAll}
        onConfirm={onConfirm}
        isPending={approveMut.isPending}
      />
    </div>
  );
}
