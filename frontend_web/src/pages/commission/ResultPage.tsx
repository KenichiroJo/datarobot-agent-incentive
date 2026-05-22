import { DownloadIcon, InfoIcon, SparklesIcon } from 'lucide-react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { getExportUrl } from '@/api/commission/api-requests';
import { useResults } from '@/api/commission/hooks';
import { KpiCard } from '@/components/commission/KpiCard';
import { COMMISSION_STEPS, Stepper } from '@/components/commission/Stepper';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { generateInsight } from '@/lib/commission-insight';

function formatYen(n: number): string {
  return n.toLocaleString('ja-JP') + ' 円';
}

const PAGE_SIZE = 50;

export function ResultPage() {
  const { sessionId = '' } = useParams<{ sessionId: string }>();
  const [page, setPage] = useState(1);
  // デフォルトは「すべて」: ReviewPage 経由していない場合でも明細が見られる
  const [filter, setFilter] = useState<'all' | 'approved' | 'hitl_pending'>('all');
  const { data, isLoading } = useResults(sessionId, { status: filter, page, perPage: PAGE_SIZE });

  const rows = data?.results ?? [];
  const summary = data?.summary;
  const insights = summary ? generateInsight(summary) : [];

  return (
    <div className="container mx-auto p-6 max-w-7xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">計算結果</h1>
          <p className="text-sm text-muted-foreground mt-1">
            確定済みデータの確認と Excel ダウンロード
          </p>
        </div>
        <Button asChild>
          <a href={getExportUrl(sessionId)} download>
            <DownloadIcon className="w-4 h-4 mr-1" />
            Excel ダウンロード
          </a>
        </Button>
      </div>

      <Card>
        <CardContent className="overflow-x-auto py-4">
          <Stepper steps={COMMISSION_STEPS} current={4} />
        </CardContent>
      </Card>

      {summary ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <KpiCard label="総レコード数" value={summary.total_records.toLocaleString('ja-JP')} />
          <KpiCard
            label="自動完了"
            value={summary.auto_completed}
            tone="success"
            hint="マスタヒット件数"
          />
          <KpiCard
            label="HITL 対象"
            value={summary.hitl_pending}
            tone="warning"
            hint="未確定 (マスタ未ヒット / 高額アラート)"
          />
          <KpiCard label="合計手数料" value={formatYen(summary.total_commission_amount)} />
        </div>
      ) : null}

      {insights.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <SparklesIcon className="w-4 h-4 text-yellow-500" />
              インサイト
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-sm leading-relaxed">
              {insights.map((line, i) => (
                <p key={i} className="text-foreground">
                  {line}
                </p>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      <TooltipProvider>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">取引先別合計</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th className="py-1">取引先</th>
                    <th className="text-right">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="inline-flex items-center gap-1 cursor-help">
                            件数
                            <InfoIcon className="w-3 h-3" />
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>
                          全レコード数（マスタヒット + 未ヒット の合算）
                        </TooltipContent>
                      </Tooltip>
                    </th>
                    <th className="text-right">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="inline-flex items-center gap-1 cursor-help">
                            合計
                            <InfoIcon className="w-3 h-3" />
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>
                          マスタヒット分のみの手数料合計（円）
                        </TooltipContent>
                      </Tooltip>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(summary?.by_partner ?? []).slice(0, 10).map((p) => (
                    <tr key={p.name} className="border-t">
                      <td className="py-1">{p.name}</td>
                      <td className="text-right py-1">{p.count}</td>
                      <td className="text-right py-1 font-mono">{formatYen(p.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">商材別合計</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th className="py-1">商材</th>
                    <th className="text-right">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="inline-flex items-center gap-1 cursor-help">
                            件数
                            <InfoIcon className="w-3 h-3" />
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>
                          全レコード数（マスタヒット + 未ヒット の合算）
                        </TooltipContent>
                      </Tooltip>
                    </th>
                    <th className="text-right">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="inline-flex items-center gap-1 cursor-help">
                            合計
                            <InfoIcon className="w-3 h-3" />
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>
                          マスタヒット分のみの手数料合計（円）
                        </TooltipContent>
                      </Tooltip>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(summary?.by_product ?? []).slice(0, 10).map((p) => (
                    <tr key={p.name} className="border-t">
                      <td className="py-1">{p.name}</td>
                      <td className="text-right py-1">{p.count}</td>
                      <td className="text-right py-1 font-mono">{formatYen(p.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      </TooltipProvider>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">明細 ({data?.total ?? 0} 件)</CardTitle>
          <div className="flex items-center gap-2">
            <select
              className="h-9 border rounded px-2 text-sm bg-background"
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value as 'all' | 'approved' | 'hitl_pending');
                setPage(1);
              }}
            >
              <option value="all">すべて</option>
              <option value="approved">確定済み (承認後)</option>
              <option value="hitl_pending">HITL 対象</option>
            </select>
          </div>
        </CardHeader>
        <CardContent>
          <div className="border rounded-md overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40">
                <tr className="text-left">
                  <th className="px-3 py-2">レコードNo</th>
                  <th className="px-3 py-2">取引先</th>
                  <th className="px-3 py-2">商材</th>
                  <th className="px-3 py-2">決済</th>
                  <th className="px-3 py-2 text-right">合計</th>
                  <th className="px-3 py-2">ステータス</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={6} className="text-center py-4 text-muted-foreground">
                      読み込み中...
                    </td>
                  </tr>
                ) : (
                  rows.map((r) => (
                    <tr key={r.record_no} className="border-t hover:bg-muted/30">
                      <td className="px-3 py-2 font-mono">{r.record_no}</td>
                      <td className="px-3 py-2">{r.partner_name ?? `#${r.partner_code}`}</td>
                      <td className="px-3 py-2">{r.product}</td>
                      <td className="px-3 py-2">{r.payment_method}</td>
                      <td className="px-3 py-2 text-right font-mono">
                        {formatYen(r.total_commission)}
                      </td>
                      <td className="px-3 py-2">
                        {r.is_anomaly ? (
                          <span className="text-yellow-700 text-xs">{r.hitl_reason}</span>
                        ) : (
                          <span className="text-green-700 text-xs">確定</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between mt-3">
            <div className="text-xs text-muted-foreground">
              ページ {page} / {Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE))}
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                前へ
              </Button>
              <Input
                type="number"
                value={page}
                className="w-20 h-9"
                onChange={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (!Number.isFinite(v)) return;
                  setPage(Math.max(1, v));
                }}
              />
              <Button
                variant="outline"
                size="sm"
                disabled={(data?.total ?? 0) <= page * PAGE_SIZE}
                onClick={() => setPage((p) => p + 1)}
              >
                次へ
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
