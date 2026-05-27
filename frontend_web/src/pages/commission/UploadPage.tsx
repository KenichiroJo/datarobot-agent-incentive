import { ArrowRightIcon, Loader2Icon } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { useUploadFiles } from '@/api/commission/hooks';
import { DropZone } from '@/components/commission/DropZone';
import { COMMISSION_STEPS, Stepper } from '@/components/commission/Stepper';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PATHS } from '@/constants/path';
import { useCommissionStore } from '@/stores/commissionStore';

function isSalesFile(name: string): boolean {
  return name.includes('売上明細') || name.includes('売上');
}
function isMasterFile(name: string): boolean {
  return name.includes('取引条件') || name.includes('マスタ');
}

export function UploadPage() {
  const navigate = useNavigate();
  const [salesFiles, setSalesFiles] = useState<File[]>([]);
  const [masterFiles, setMasterFiles] = useState<File[]>([]);
  const uploadMut = useUploadFiles();
  const setSession = useCommissionStore((s) => s.setSession);
  const setFilenames = useCommissionStore((s) => s.setFilenames);
  const clearLog = useCommissionStore((s) => s.clearLog);

  const hasMinimum = salesFiles.length > 0 && masterFiles.length > 0;

  const onConfirm = async () => {
    const allFiles = [...salesFiles, ...masterFiles];
    try {
      const res = await uploadMut.mutateAsync(allFiles);
      setSession(res.session_id);
      setFilenames(res.uploaded.map((u) => u.filename));
      clearLog();
      toast.success(`${res.uploaded.length} ファイル受領しました`);
      navigate(PATHS.COMMISSION.CALCULATE.replace(':sessionId', res.session_id));
    } catch (e) {
      toast.error('アップロード失敗: ' + (e instanceof Error ? e.message : String(e)));
    }
  };

  return (
    <div className="container mx-auto p-6 max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">ファイルアップロード</h1>
        <p className="text-sm text-muted-foreground mt-1">
          売上明細 Excel と取引条件マスタ Excel をそれぞれアップロードしてください
        </p>
      </div>

      <Card>
        <CardContent className="overflow-x-auto py-4">
          <Stepper steps={COMMISSION_STEPS} current={0} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card data-tour="upload-zone-sales">
          <CardHeader>
            <CardTitle className="text-base">売上明細</CardTitle>
          </CardHeader>
          <CardContent>
            <DropZone
              label="売上明細 Excel"
              description="ファイル名に「売上明細」を含むことを推奨"
              accept=".xlsx,.xls,.csv"
              onFilesAdded={(files) => {
                const valid = files.filter((f) => isSalesFile(f.name) || !isMasterFile(f.name));
                setSalesFiles((prev) => [...prev, ...valid]);
              }}
              existingFiles={salesFiles.map((f) => f.name)}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">取引条件マスタ</CardTitle>
          </CardHeader>
          <CardContent>
            <DropZone
              label="取引条件マスタ Excel"
              description="ファイル名に「取引条件」または「マスタ」を含むことを推奨"
              accept=".xlsx,.xls,.csv"
              onFilesAdded={(files) => {
                setMasterFiles((prev) => [...prev, ...files]);
              }}
              existingFiles={masterFiles.map((f) => f.name)}
            />
          </CardContent>
        </Card>
      </div>

      <div className="flex justify-end">
        <Button
          onClick={onConfirm}
          disabled={!hasMinimum || uploadMut.isPending}
          data-tour="calculate-start"
        >
          {uploadMut.isPending ? (
            <Loader2Icon className="w-4 h-4 mr-1 animate-spin" />
          ) : null}
          計算を開始する
          <ArrowRightIcon className="w-4 h-4 ml-1" />
        </Button>
      </div>
    </div>
  );
}
