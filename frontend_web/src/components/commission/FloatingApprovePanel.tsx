import { Loader2Icon } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

interface FloatingApprovePanelProps {
  selectedCount: number;
  decidedCount: number;
  totalCount: number;
  onApproveAll: () => void;
  onConfirm: () => void;
  isPending?: boolean;
}

export function FloatingApprovePanel({
  selectedCount,
  decidedCount,
  totalCount,
  onApproveAll,
  onConfirm,
  isPending,
}: FloatingApprovePanelProps) {
  return (
    <Card className="fixed bottom-6 right-6 px-4 py-3 shadow-lg z-50 flex items-center gap-4 max-w-md">
      <div className="text-sm">
        <div className="font-medium">HITL 承認状況</div>
        <div className="text-xs text-muted-foreground">
          選択 {selectedCount} 件 / 決定済 {decidedCount} 件 / 全 {totalCount} 件
        </div>
      </div>
      <Button variant="outline" size="sm" onClick={onApproveAll}>
        全件承認
      </Button>
      <Button size="sm" onClick={onConfirm} disabled={decidedCount === 0 || isPending}>
        {isPending ? <Loader2Icon className="w-4 h-4 mr-1 animate-spin" /> : null}
        確定する
      </Button>
    </Card>
  );
}
