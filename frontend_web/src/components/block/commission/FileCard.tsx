// アップロード済みファイルを表示するカード

import { CheckCircle2, FileSpreadsheet } from 'lucide-react';
import { Card } from '@/components/ui/card';

import type { UploadedFileInfo } from '@/api/commission/types';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const TYPE_LABEL: Record<string, string> = {
  sales: '売上明細',
  master: '取引条件マスタ',
  unknown: '種別未判定',
};

interface FileCardProps {
  file: UploadedFileInfo;
}

export function FileCard({ file }: FileCardProps) {
  return (
    <Card className="flex items-center gap-3 p-4">
      <FileSpreadsheet className="size-8 shrink-0 text-[var(--commission-primary)]" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold">{file.filename}</div>
        <div className="text-xs text-muted-foreground">
          {formatBytes(file.size)} · 検出種別: <span className="font-medium">{TYPE_LABEL[file.detected_type] ?? file.detected_type}</span>
        </div>
      </div>
      <CheckCircle2 className="size-5 shrink-0 text-[var(--commission-success)]" />
    </Card>
  );
}
