// 取引先別 / 商材別 集計テーブル

import { Card } from '@/components/ui/card';

interface AggregatedTableProps {
  title: string;
  rows: { name: string; recordCount: number; totalCommission: number }[];
}

function formatYen(n: number): string {
  return `¥${n.toLocaleString('ja-JP')}`;
}

export function AggregatedTable({ title, rows }: AggregatedTableProps) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b bg-muted/30 px-4 py-2 text-sm font-semibold">{title}</div>
      <div className="max-h-64 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/20 text-xs uppercase">
            <tr>
              <th className="px-3 py-2 text-left">名称</th>
              <th className="px-3 py-2 text-right">件数</th>
              <th className="px-3 py-2 text-right">合計</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-3 py-4 text-center text-muted-foreground">
                  データなし
                </td>
              </tr>
            ) : null}
            {rows.map((r) => (
              <tr key={r.name} className="border-t hover:bg-muted/20">
                <td className="truncate px-3 py-2">{r.name}</td>
                <td className="px-3 py-2 text-right font-mono">{r.recordCount.toLocaleString()}</td>
                <td className="px-3 py-2 text-right font-mono">{formatYen(r.totalCommission)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
