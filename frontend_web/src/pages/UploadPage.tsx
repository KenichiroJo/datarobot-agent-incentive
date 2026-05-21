// ファイルアップロード画面: 売上明細 / 取引条件マスタ用の 2 ドロップゾーン

import { useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

import { useUploadFiles } from '@/api/commission/hooks';
import { FileCard } from '@/components/block/commission/FileCard';
import { FileDropzone } from '@/components/block/commission/FileDropzone';
import { Button } from '@/components/ui/button';
import { PATHS } from '@/constants/path';
import { useCommissionSession } from '@/store/commission-session-store';
import { toast } from 'sonner';

export default function UploadPage() {
  const navigate = useNavigate();
  const sessionId = useCommissionSession((s) => s.sessionId);
  const setSessionId = useCommissionSession((s) => s.setSessionId);
  const uploadedFiles = useCommissionSession((s) => s.uploadedFiles);
  const setUploadedFile = useCommissionSession((s) => s.setUploadedFile);
  const upload = useUploadFiles();

  const ready = Boolean(uploadedFiles.sales && uploadedFiles.master);

  const handleUpload = async (file: File) => {
    try {
      const res = await upload.mutateAsync({
        files: [file],
        sessionId: sessionId ?? undefined,
      });
      if (!sessionId) setSessionId(res.session_id);
      for (const info of res.uploaded) {
        if (info.detected_type === 'sales' || info.detected_type === 'master') {
          setUploadedFile(info.detected_type, info);
          toast.success(`${info.filename} をアップロードしました`);
        } else {
          toast.warning(`${info.filename} は種別を判定できませんでした`);
        }
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'アップロードに失敗しました';
      toast.error(msg);
    }
  };

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-bold text-[var(--commission-text-primary)]">
          ファイルアップロード
        </h1>
        <p className="text-sm text-[var(--commission-text-muted)]">
          売上明細 Excel と取引条件マスタ Excel をアップロードしてください。
        </p>
      </header>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-3">
          <FileDropzone
            label="売上明細 Excel"
            description="月次の売上明細データ (※「売上」を含むファイル名で自動判定)"
            onFile={handleUpload}
            disabled={upload.isPending}
          />
          {uploadedFiles.sales ? <FileCard file={uploadedFiles.sales} /> : null}
        </div>
        <div className="space-y-3">
          <FileDropzone
            label="取引条件マスタ Excel"
            description="取引先別のコミッション条件マスタ (※「取引条件」「マスタ」を含むファイル名で自動判定)"
            onFile={handleUpload}
            disabled={upload.isPending}
          />
          {uploadedFiles.master ? <FileCard file={uploadedFiles.master} /> : null}
        </div>
      </div>

      <div className="flex justify-end">
        <Button
          size="lg"
          disabled={!ready}
          onClick={() => navigate(PATHS.COMMISSION.CALCULATE)}
        >
          計算を開始する
          <ArrowRight className="ml-1 size-4" />
        </Button>
      </div>
    </div>
  );
}
