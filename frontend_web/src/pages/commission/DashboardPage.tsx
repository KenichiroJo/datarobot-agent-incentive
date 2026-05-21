import { ArrowRightIcon } from 'lucide-react';
import { Link } from 'react-router-dom';

import { useDashboard } from '@/api/commission/hooks';
import { KpiCard } from '@/components/commission/KpiCard';
import { COMMISSION_STEPS, Stepper } from '@/components/commission/Stepper';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PATHS } from '@/constants/path';
import { useCommissionStore } from '@/stores/commissionStore';

function formatYen(n: number): string {
  return n.toLocaleString('ja-JP') + ' 円';
}

export function DashboardPage() {
  const sessionId = useCommissionStore((s) => s.currentSessionId);
  const { data, isLoading } = useDashboard(sessionId ?? undefined);

  const kpi = data?.kpi ?? {
    total_records: 0,
    auto_completed: 0,
    hitl_pending: 0,
    hitl_approved: 0,
    error_count: 0,
    total_commission_amount: 0,
    auto_completion_rate: 0,
  };

  return (
    <div className="container mx-auto p-6 max-w-7xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">販売管理手数料 ダッシュボード</h1>
          <p className="text-sm text-muted-foreground mt-1">
            ウォーターサーバー販売代理店の月次手数料を AI エージェントで自動計算
          </p>
        </div>
        <Button asChild>
          <Link to={PATHS.COMMISSION.UPLOAD}>
            新規計算を開始
            <ArrowRightIcon className="w-4 h-4 ml-1" />
          </Link>
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KpiCard
          label="総処理件数"
          value={isLoading ? '...' : kpi.total_records.toLocaleString('ja-JP')}
          hint="今月の売上明細"
        />
        <KpiCard
          label="自動完了率"
          value={`${(kpi.auto_completion_rate * 100).toFixed(1)}%`}
          tone="success"
          hint={`${kpi.auto_completed} 件 / ${kpi.total_records} 件`}
        />
        <KpiCard
          label="HITL 待ち"
          value={kpi.hitl_pending}
          tone={kpi.hitl_pending > 0 ? 'warning' : 'default'}
          hint="人間が確認すべき件数"
        />
        <KpiCard
          label="手数料合計"
          value={formatYen(kpi.total_commission_amount)}
          hint="確定済み手数料"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">処理フェーズ</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto py-4">
          <Stepper steps={COMMISSION_STEPS} current={sessionId ? 0 : -1} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">取引先別 (上位 5)</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="py-1">取引先</th>
                  <th className="text-right">件数</th>
                  <th className="text-right">合計</th>
                </tr>
              </thead>
              <tbody>
                {(data?.by_partner ?? []).slice(0, 5).map((p) => (
                  <tr key={p.name} className="border-t">
                    <td className="py-1">{p.name}</td>
                    <td className="text-right py-1">{p.count}</td>
                    <td className="text-right py-1 font-mono">{formatYen(p.total)}</td>
                  </tr>
                ))}
                {(data?.by_partner?.length ?? 0) === 0 ? (
                  <tr>
                    <td colSpan={3} className="text-center py-4 text-muted-foreground">
                      データなし
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">商材別 (上位 5)</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="py-1">商材</th>
                  <th className="text-right">件数</th>
                  <th className="text-right">合計</th>
                </tr>
              </thead>
              <tbody>
                {(data?.by_product ?? []).slice(0, 5).map((p) => (
                  <tr key={p.name} className="border-t">
                    <td className="py-1">{p.name}</td>
                    <td className="text-right py-1">{p.count}</td>
                    <td className="text-right py-1 font-mono">{formatYen(p.total)}</td>
                  </tr>
                ))}
                {(data?.by_product?.length ?? 0) === 0 ? (
                  <tr>
                    <td colSpan={3} className="text-center py-4 text-muted-foreground">
                      データなし
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
