// 商材別合計のドーナツチャート (recharts)

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import type { ProductAggregate } from '@/api/commission/types';

interface DonutChartProps {
  data: ProductAggregate[];
}

const COLORS = ['#1B3A6B', '#2563EB', '#16A34A', '#F59E0B', '#DC2626', '#7C3AED', '#0891B2'];

function formatYen(n: number): string {
  return `¥${n.toLocaleString('ja-JP')}`;
}

export function CommissionDonutChart({ data }: DonutChartProps) {
  if (!data.length) {
    return (
      <div className="flex h-64 items-center justify-center rounded-md border bg-card text-sm text-muted-foreground">
        確定済みデータがありません
      </div>
    );
  }
  return (
    <div className="h-64 w-full rounded-md border bg-card p-4">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="total_commission"
            nameKey="product"
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={80}
            paddingAngle={2}
          >
            {data.map((_, idx) => (
              <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: unknown, name: unknown) => [
              formatYen(typeof value === 'number' ? value : 0),
              String(name),
            ]}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
