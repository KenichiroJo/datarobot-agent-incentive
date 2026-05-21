import { FileSpreadsheetIcon, UploadIcon } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';

import { cn } from '@/lib/utils';

interface DropZoneProps {
  label: string;
  description?: string;
  accept?: string;
  /** ファイルが追加されたとき。複数選択時は files 配列を渡す */
  onFilesAdded: (files: File[]) => void;
  /** 既にアップロード済みのファイル名（表示用） */
  existingFiles?: string[];
}

export function DropZone({
  label,
  description,
  accept = '.xlsx,.xls,.csv',
  onFilesAdded,
  existingFiles = [],
}: DropZoneProps) {
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      onFilesAdded(Array.from(files));
    },
    [onFilesAdded]
  );

  return (
    <div
      onDragEnter={(e) => {
        e.preventDefault();
        setDragActive(true);
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragActive(false);
        handleFiles(e.dataTransfer.files);
      }}
      onClick={() => inputRef.current?.click()}
      className={cn(
        'relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors',
        dragActive ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      <div className="flex flex-col items-center gap-2">
        <UploadIcon className="w-8 h-8 text-muted-foreground" />
        <div className="font-medium">{label}</div>
        {description ? (
          <div className="text-sm text-muted-foreground">{description}</div>
        ) : null}
        <div className="text-xs text-muted-foreground">
          クリックまたはドラッグ&ドロップ ({accept})
        </div>
      </div>
      {existingFiles.length > 0 ? (
        <div className="mt-4 flex flex-col gap-1 items-center">
          {existingFiles.map((name) => (
            <div
              key={name}
              className="flex items-center gap-2 text-sm text-foreground bg-muted/50 px-2 py-1 rounded"
            >
              <FileSpreadsheetIcon className="w-4 h-4" />
              <span className="truncate max-w-xs">{name}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
