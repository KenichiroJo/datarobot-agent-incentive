// HITL レビューテーブル
// 列: チェックボックス / レコードNo / 取引先名称 / 商材 / 決済方法 / 計算結果(¥) /
//     異常理由 / 計算根拠 (accordion) / アクション (承認/却下/手動入力)

import { useState } from 'react';
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, XCircle } from 'lucide-react';

import type { ResultRecord, AnomalyType } from '@/api/commission/types';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';

export interface HitlDecisionMap {
  [recordNo: string]: { action: 'approve' | 'reject' | 'manual'; manualAmount?: number };
}

interface HitlReviewTableProps {
  records: ResultRecord[];
  decisions: HitlDecisionMap;
  selected: Set<string>;
  onSelectionChange: (selected: Set<string>) => void;
  onDecisionChange: (recordNo: string, decision: { action: 'approve' | 'reject' | 'manual'; manualAmount?: number } | null) => void;
}

const REASON_LABEL: Record<AnomalyType, { label: string; color: string; Icon: typeof AlertTriangle }> = {
  master_not_found: { label: 'マスタ未ヒット', color: 'text-[var(--commission-danger)]', Icon: XCircle },
  high_amount: { label: '高額アラート', color: 'text-[var(--commission-warning)]', Icon: AlertTriangle },
  calc_error: { label: '計算エラー', color: 'text-orange-600', Icon: AlertTriangle },
};

function formatYen(n: number): string {
  return `¥${n.toLocaleString('ja-JP')}`;
}

export function HitlReviewTable({
  records,
  decisions,
  selected,
  onSelectionChange,
  onDecisionChange,
}: HitlReviewTableProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggleSelected = (rno: string) => {
    const next = new Set(selected);
    if (next.has(rno)) next.delete(rno);
    else next.add(rno);
    onSelectionChange(next);
  };

  const toggleExpanded = (rno: string) => {
    const next = new Set(expanded);
    if (next.has(rno)) next.delete(rno);
    else next.add(rno);
    setExpanded(next);
  };

  const allSelected =
    records.length > 0 && records.every((r) => selected.has(String(r.record_no ?? '')));

  const toggleAll = () => {
    if (allSelected) {
      onSelectionChange(new Set());
    } else {
      onSelectionChange(new Set(records.map((r) => String(r.record_no ?? ''))));
    }
  };

  return (
    <div className="overflow-x-auto rounded-md border bg-card">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-xs uppercase">
          <tr>
            <th className="w-10 px-2 py-2 text-left">
              <Checkbox
                checked={allSelected}
                onCheckedChange={toggleAll}
                aria-label="すべて選択"
              />
            </th>
            <th className="px-2 py-2 text-left">レコードNo</th>
            <th className="px-2 py-2 text-left">取引先</th>
            <th className="px-2 py-2 text-left">商材</th>
            <th className="px-2 py-2 text-left">決済</th>
            <th className="px-2 py-2 text-right">計算結果</th>
            <th className="px-2 py-2 text-left">異常理由</th>
            <th className="px-2 py-2 text-left">根拠</th>
            <th className="px-2 py-2 text-left">アクション</th>
          </tr>
        </thead>
        <tbody>
          {records.length === 0 ? (
            <tr>
              <td colSpan={9} className="px-2 py-6 text-center text-muted-foreground">
                対象レコードはありません。
              </td>
            </tr>
          ) : null}
          {records.map((r) => {
            const rno = String(r.record_no ?? '');
            const isSel = selected.has(rno);
            const isExp = expanded.has(rno);
            const decision = decisions[rno];
            const reasonKey: AnomalyType = (r.hitl_reason ?? 'master_not_found') as AnomalyType;
            const reasonDef = REASON_LABEL[reasonKey] ?? REASON_LABEL.master_not_found;
            const Icon = reasonDef.Icon;
            return (
              <>
                <tr
                  key={rno}
                  className={cn(
                    'border-t hover:bg-muted/30',
                    decision?.action === 'approve' && 'bg-[var(--commission-success)]/5',
                    decision?.action === 'reject' && 'bg-[var(--commission-danger)]/5',
                  )}
                >
                  <td className="px-2 py-2">
                    <Checkbox
                      checked={isSel}
                      onCheckedChange={() => toggleSelected(rno)}
                      aria-label={`レコード ${rno} 選択`}
                    />
                  </td>
                  <td className="px-2 py-2 font-mono text-xs">{rno || '-'}</td>
                  <td className="px-2 py-2">{r.partner_name ?? '(未確定)'}</td>
                  <td className="px-2 py-2">{r.product ?? '-'}</td>
                  <td className="px-2 py-2">{r.payment_method ?? '-'}</td>
                  <td className="px-2 py-2 text-right font-mono">
                    {decision?.action === 'manual' && typeof decision.manualAmount === 'number'
                      ? formatYen(decision.manualAmount)
                      : formatYen(r.total_commission)}
                  </td>
                  <td className="px-2 py-2">
                    <span className={cn('inline-flex items-center gap-1 text-xs', reasonDef.color)}>
                      <Icon className="size-3.5" />
                      {r.hitl_reason_ja ?? reasonDef.label}
                    </span>
                  </td>
                  <td className="px-2 py-2">
                    <button
                      type="button"
                      onClick={() => toggleExpanded(rno)}
                      className="inline-flex items-center text-xs text-[var(--commission-accent)] hover:underline"
                    >
                      {isExp ? (
                        <ChevronDown className="size-3.5" />
                      ) : (
                        <ChevronRight className="size-3.5" />
                      )}
                      根拠
                    </button>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex flex-wrap gap-1">
                      <Button
                        size="sm"
                        variant={decision?.action === 'approve' ? 'primary' : 'secondary'}
                        onClick={() => onDecisionChange(rno, { action: 'approve' })}
                      >
                        <CheckCircle2 className="size-3" />
                        承認
                      </Button>
                      <Button
                        size="sm"
                        variant={decision?.action === 'reject' ? 'destructive' : 'secondary'}
                        onClick={() => onDecisionChange(rno, { action: 'reject' })}
                      >
                        <XCircle className="size-3" />
                        却下
                      </Button>
                      <Button
                        size="sm"
                        variant={decision?.action === 'manual' ? 'primary' : 'secondary'}
                        onClick={() =>
                          onDecisionChange(rno, {
                            action: 'manual',
                            manualAmount: r.total_commission,
                          })
                        }
                      >
                        手動入力
                      </Button>
                    </div>
                    {decision?.action === 'manual' ? (
                      <input
                        type="number"
                        value={decision.manualAmount ?? 0}
                        onChange={(e) =>
                          onDecisionChange(rno, {
                            action: 'manual',
                            manualAmount: Number(e.target.value),
                          })
                        }
                        className="mt-1 w-24 rounded border bg-background px-2 py-1 text-xs"
                      />
                    ) : null}
                  </td>
                </tr>
                {isExp ? (
                  <tr key={`${rno}-trace`}>
                    <td />
                    <td colSpan={8} className="bg-muted/20 px-2 py-3 text-xs">
                      <div className="font-semibold">計算根拠 (calculation_trace)</div>
                      <ul className="mt-1 space-y-0.5 font-mono text-[0.7rem]">
                        {(r.calculation_trace ?? []).map((t, i) => (
                          <li key={i}>{t}</li>
                        ))}
                      </ul>
                      {r.master_key_used ? (
                        <div className="mt-2 text-xs text-muted-foreground">
                          使用キー: <span className="font-mono">{r.master_key_used}</span>
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ) : null}
              </>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
