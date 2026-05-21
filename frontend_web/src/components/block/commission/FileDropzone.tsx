// 単一ファイル用のドラッグ＆ドロップ受付エリア (react-dropzone)

import { useDropzone } from 'react-dropzone';
import { Upload as UploadIcon } from 'lucide-react';

import { cn } from '@/lib/utils';

interface FileDropzoneProps {
  label: string;
  description: string;
  onFile: (file: File) => void;
  accept?: string[];
  disabled?: boolean;
}

const DEFAULT_ACCEPT_MIME: Record<string, string[]> = {
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'application/vnd.ms-excel': ['.xls'],
  'text/csv': ['.csv'],
};

export function FileDropzone({ label, description, onFile, disabled }: FileDropzoneProps) {
  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    accept: DEFAULT_ACCEPT_MIME,
    multiple: false,
    disabled,
    onDrop: (accepted) => {
      if (accepted[0]) onFile(accepted[0]);
    },
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 transition-colors',
        'cursor-pointer text-center',
        isDragActive
          ? 'border-[var(--commission-accent)] bg-[var(--commission-accent)]/5'
          : 'border-muted-foreground/30 bg-card hover:border-[var(--commission-accent)]/60',
        isDragReject ? 'border-[var(--commission-danger)] bg-[var(--commission-danger)]/5' : '',
        disabled ? 'pointer-events-none opacity-50' : '',
      )}
    >
      <input {...getInputProps()} />
      <UploadIcon className="mb-3 size-10 text-[var(--commission-accent)]" />
      <div className="text-base font-semibold text-[var(--commission-text-primary)]">{label}</div>
      <p className="mt-1 text-sm text-[var(--commission-text-muted)]">{description}</p>
      <p className="mt-3 text-xs text-muted-foreground">
        ドラッグ&ドロップ または クリックでファイル選択 (xlsx / csv)
      </p>
    </div>
  );
}
