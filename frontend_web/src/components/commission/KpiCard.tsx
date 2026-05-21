import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface KpiCardProps {
  label: string;
  value: string | number;
  hint?: string;
  tone?: 'default' | 'success' | 'warning' | 'danger';
}

export function KpiCard({ label, value, hint, tone = 'default' }: KpiCardProps) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-1">
        <CardTitle className="text-xs font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div
          className={cn(
            'text-2xl font-bold',
            tone === 'success' && 'text-green-600',
            tone === 'warning' && 'text-yellow-600',
            tone === 'danger' && 'text-red-600'
          )}
        >
          {value}
        </div>
        {hint ? <div className="text-xs text-muted-foreground mt-1">{hint}</div> : null}
      </CardContent>
    </Card>
  );
}
