import { ChevronDownIcon, ChevronRightIcon, InfoIcon } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { useCommissionStore } from '@/stores/commissionStore';
import { cn } from '@/lib/utils';

import type { CommissionResult, HitlAction } from '@/api/commission/types';

interface AnomalyTableProps {
  rows: CommissionResult[];
}

function formatYen(n: number): string {
  return n.toLocaleString('ja-JP') + ' 円';
}

export function AnomalyTable({ rows }: AnomalyTableProps) {
  const decisions = useCommissionStore((s) => s.decisions);
  const setDecision = useCommissionStore((s) => s.setDecision);
  const selected = useCommissionStore((s) => s.selectedRecords);
  const toggleSelected = useCommissionStore((s) => s.toggleSelected);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const onAction = (record: CommissionResult, action: HitlAction) => {
    setDecision(record.record_no, { action });
  };

  const onManualChange = (record: CommissionResult, value: string) => {
    const amount = parseFloat(value);
    setDecision(record.record_no, {
      action: 'manual',
      manual_amount: Number.isFinite(amount) ? amount : 0,
    });
  };

  const toggleExpand = (recordNo: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(recordNo)) next.delete(recordNo);
      else next.add(recordNo);
      return next;
    });
  };

  return (
    <div className="border rounded-md overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-muted/40">
          <tr className="text-left">
            <th className="px-3 py-2 w-10"></th>
            <th className="px-3 py-2 w-10"></th>
            <th className="px-3 py-2">レコードNo</th>
            <th className="px-3 py-2">取引先</th>
            <th className="px-3 py-2">商材</th>
            <th className="px-3 py-2">決済</th>
            <th className="px-3 py-2 text-right">計算結果</th>
            <th className="px-3 py-2">異常理由</th>
            <th className="px-3 py-2">アクション</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const isOpen = expanded.has(r.record_no);
            const dec = decisions[r.record_no];
            const isSelected = selected.includes(r.record_no);
            return (
              <>
                <tr
                  key={r.record_no}
                  className={cn(
                    'border-t hover:bg-muted/30',
                    dec?.action === 'approve' && 'bg-green-50/50',
                    dec?.action === 'reject' && 'bg-red-50/50',
                    dec?.action === 'manual' && 'bg-yellow-50/50'
                  )}
                >
                  <td className="px-3 py-2">
                    <Checkbox
                      checked={isSelected}
                      onCheckedChange={() => toggleSelected(r.record_no)}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={() => toggleExpand(r.record_no)}
                      className="text-muted-foreground hover:text-foreground"
                      aria-label="トレース展開"
                    >
                      {isOpen ? (
                        <ChevronDownIcon className="w-4 h-4" />
                      ) : (
                        <ChevronRightIcon className="w-4 h-4" />
                      )}
                    </button>
                  </td>
                  <td className="px-3 py-2 font-mono">{r.record_no}</td>
                  <td className="px-3 py-2">{r.partner_name ?? `#${r.partner_code}`}</td>
                  <td className="px-3 py-2">{r.product}</td>
                  <td className="px-3 py-2">{r.payment_method}</td>
                  <td className="px-3 py-2 text-right font-mono">
                    {formatYen(r.total_commission)}
                  </td>
                  <td className="px-3 py-2">
                    <Badge
                      variant={!r.master_found ? 'destructive' : 'secondary'}
                      className="text-xs"
                    >
                      {r.hitl_reason ?? '-'}
                    </Badge>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex gap-1 flex-wrap">
                      <Button
                        size="sm"
                        variant={dec?.action === 'approve' ? 'default' : 'outline'}
                        onClick={() => onAction(r, 'approve')}
                      >
                        承認
                      </Button>
                      <Button
                        size="sm"
                        variant={dec?.action === 'reject' ? 'destructive' : 'outline'}
                        onClick={() => onAction(r, 'reject')}
                      >
                        却下
                      </Button>
                      <Input
                        className="w-24 h-8"
                        type="number"
                        placeholder="手動入力"
                        value={
                          dec?.action === 'manual' && dec.manual_amount !== undefined
                            ? String(dec.manual_amount)
                            : ''
                        }
                        onChange={(e) => onManualChange(r, e.target.value)}
                      />
                    </div>
                  </td>
                </tr>
                {isOpen ? (
                  <tr key={`${r.record_no}-trace`} className="bg-muted/20">
                    <td colSpan={9} className="px-6 py-3">
                      <div className="flex items-start gap-2 text-xs">
                        <InfoIcon className="w-4 h-4 mt-0.5 text-muted-foreground" />
                        <pre className="whitespace-pre-wrap font-mono text-xs">
                          {r.calculation_trace.join('\n')}
                        </pre>
                      </div>
                    </td>
                  </tr>
                ) : null}
              </>
            );
          })}
        </tbody>
      </table>
      {rows.length === 0 ? (
        <div className="p-8 text-center text-muted-foreground">該当データがありません</div>
      ) : null}
    </div>
  );
}
