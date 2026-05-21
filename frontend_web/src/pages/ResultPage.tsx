// 計算結果ページ: 集計テーブル + ドーナツチャート + 全レコードページネーション

import { useMemo, useState } from 'react';
import { Download } from 'lucide-react';

import { useDashboard, useExportCsv, useResults } from '@/api/commission/hooks';
import { AggregatedTable } from '@/components/block/commission/AggregatedTable';
import { CommissionDonutChart } from '@/components/block/commission/CommissionDonutChart';
import { Button } from '@/components/ui/button';
import { useCommissionSession } from '@/store/commission-session-store';
import { toast } from 'sonner';

function formatYen(n: number): string {
  return `¥${n.toLocaleString('ja-JP')}`;
}

export default function ResultPage() {
  const sessionId = useCommissionSession((s) => s.sessionId);
  const dashboard = useDashboard(sessionId, Boolean(sessionId));
  const exportMutation = useExportCsv();

  const [page, setPage] = useState(1);
  const [partnerFilter, setPartnerFilter] = useState('');
  const [productFilter, setProductFilter] = useState('');
  const perPage = 50;

  const { data: results, isLoading } = useResults(
    sessionId,
    { status: 'all', page, per_page: perPage },
    Boolean(sessionId),
  );

  const filteredRows = useMemo(() => {
    const rows = results?.records ?? [];
    return rows.filter((r) => {
      if (partnerFilter && !(r.partner_name ?? '').includes(partnerFilter)) return false;
      if (productFilter && !(r.product ?? '').includes(productFilter)) return false;
      return true;
    });
  }, [results?.records, partnerFilter, productFilter]);

  const total = results?.total ?? 0;
  const lastPage = Math.max(1, Math.ceil(total / perPage));

  const handleExport = async () => {
    if (!sessionId) return;
    try {
      await exportMutation.mutateAsync(sessionId);
      toast.success('CSV をダウンロードしました');
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'ダウンロードに失敗しました';
      toast.error(msg);
    }
  };

  const byPartner = (dashboard.data?.by_partner ?? []).map((p) => ({
    name: p.partner,
    recordCount: p.record_count,
    totalCommission: p.total_commission,
  }));
  const byProduct = dashboard.data?.by_product ?? [];

  return (
    <div className="space-y-6 p-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--commission-text-primary)]">計算結果</h1>
          <p className="text-sm text-[var(--commission-text-muted)]">
            {dashboard.data
              ? `${dashboard.data.kpi.total_records.toLocaleString()} 件 / 合計 ${formatYen(dashboard.data.kpi.total_commission_amount)}`
              : '読み込み中…'}
          </p>
        </div>
        <Button onClick={handleExport} disabled={!sessionId || exportMutation.isPending}>
          <Download className="size-4" />
          CSV ダウンロード
        </Button>
      </header>

      <section className="grid gap-4 md:grid-cols-2">
        <AggregatedTable title="取引先別合計" rows={byPartner} />
        <div className="space-y-2">
          <div className="text-sm font-semibold">商材別合計 (ドーナツ)</div>
          <CommissionDonutChart data={byProduct} />
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-sm font-semibold">全レコード ({total.toLocaleString()} 件)</h2>
          <input
            type="text"
            placeholder="取引先で絞り込み"
            value={partnerFilter}
            onChange={(e) => setPartnerFilter(e.target.value)}
            className="rounded border bg-background px-2 py-1 text-xs"
          />
          <input
            type="text"
            placeholder="商材で絞り込み"
            value={productFilter}
            onChange={(e) => setProductFilter(e.target.value)}
            className="rounded border bg-background px-2 py-1 text-xs"
          />
        </div>

        {isLoading ? (
          <div className="rounded-md border bg-card p-6 text-center text-sm text-muted-foreground">
            読み込み中…
          </div>
        ) : (
          <div className="overflow-x-auto rounded-md border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase">
                <tr>
                  <th className="px-2 py-2 text-left">レコードNo</th>
                  <th className="px-2 py-2 text-left">取引先</th>
                  <th className="px-2 py-2 text-left">商材</th>
                  <th className="px-2 py-2 text-left">決済</th>
                  <th className="px-2 py-2 text-right">基本</th>
                  <th className="px-2 py-2 text-right">合計</th>
                  <th className="px-2 py-2 text-left">ステータス</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((r) => (
                  <tr key={String(r.record_no)} className="border-t hover:bg-muted/20">
                    <td className="px-2 py-1.5 font-mono text-xs">{r.record_no}</td>
                    <td className="px-2 py-1.5">{r.partner_name ?? '-'}</td>
                    <td className="px-2 py-1.5">{r.product ?? '-'}</td>
                    <td className="px-2 py-1.5">{r.payment_method ?? '-'}</td>
                    <td className="px-2 py-1.5 text-right font-mono">{formatYen(r.basic_commission)}</td>
                    <td className="px-2 py-1.5 text-right font-mono font-semibold">
                      {formatYen(r.total_commission)}
                    </td>
                    <td className="px-2 py-1.5 text-xs">{r.status}</td>
                  </tr>
                ))}
                {filteredRows.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-2 py-6 text-center text-muted-foreground">
                      該当レコードがありません
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between text-xs">
          <span>
            ページ {page} / {lastPage}
          </span>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              前へ
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setPage((p) => Math.min(lastPage, p + 1))}
              disabled={page >= lastPage}
            >
              次へ
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
