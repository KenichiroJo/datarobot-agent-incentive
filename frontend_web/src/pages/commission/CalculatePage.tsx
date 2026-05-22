import { Loader2Icon } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';

import { streamCalculate } from '@/api/commission/api-requests';
import { COMMISSION_STEPS, Stepper } from '@/components/commission/Stepper';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PATHS } from '@/constants/path';
import { useCommissionStore } from '@/stores/commissionStore';

export function CalculatePage() {
  const { sessionId = '' } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const appendLog = useCommissionStore((s) => s.appendLog);
  const log = useCommissionStore((s) => s.progressLog);
  const setSession = useCommissionStore((s) => s.setSession);
  const [done, setDone] = useState(false);
  const [hasError, setHasError] = useState(false);
  const startedRef = useRef(false);
  const terminalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [log]);

  useEffect(() => {
    if (startedRef.current || !sessionId) return;
    startedRef.current = true;
    setSession(sessionId);

    appendLog(`[start] セッション ${sessionId.slice(0, 8)}... の計算を開始`);

    // NOTE: AbortController は使わない。React StrictMode のダブルマウントで
    // 接続が即座に abort される問題を回避するため、fire-and-forget で実行。
    // ストリーム終了は done / error イベントで自然終了する。
    streamCalculate(sessionId, {
      onEvent: (event, data) => {
        const payload = data as Record<string, unknown>;
        if (event === 'progress' || event === 'status') {
          const msg =
            (payload.message as string | undefined) ??
            (payload.node ? `${payload.node} 完了` : 'イベント受信');
          appendLog(`[${event}] ${msg}`);
        } else if (event === 'hitl_required') {
          const count = (payload.payload as { pending_count?: number })?.pending_count ?? '?';
          appendLog(`[hitl] 人間確認が必要なレコード: ${count} 件`);
          setDone(true);
          setTimeout(() => {
            navigate(PATHS.COMMISSION.REVIEW.replace(':sessionId', sessionId));
          }, 800);
        } else if (event === 'result') {
          const summary = (payload as { summary?: { total_records?: number } }).summary;
          appendLog(`[result] 計算完了 合計 ${summary?.total_records ?? '?'} 件`);
        } else if (event === 'done') {
          appendLog('[done] ストリーム終了');
          setDone(true);
          setTimeout(() => {
            navigate(PATHS.COMMISSION.RESULT.replace(':sessionId', sessionId));
          }, 800);
        } else if (event === 'error') {
          appendLog(`[error] ${payload.message ?? 'unknown error'}`);
          setHasError(true);
          toast.error('計算でエラーが発生しました');
        }
      },
    }).catch((e: unknown) => {
      if ((e as { name?: string }).name === 'AbortError') return;
      appendLog(`[exception] ${e instanceof Error ? e.message : String(e)}`);
      setHasError(true);
    });
  }, [sessionId, appendLog, navigate, setSession]);

  return (
    <div className="container mx-auto p-6 max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">手数料計算 実行中</h1>
        <p className="text-sm text-muted-foreground mt-1">
          AI エージェントが売上明細を取引条件マスタと突合して計算しています
        </p>
      </div>

      <Card>
        <CardContent className="overflow-x-auto py-4">
          <Stepper steps={COMMISSION_STEPS} current={2} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            {!done && !hasError ? <Loader2Icon className="w-4 h-4 animate-spin" /> : null}
            実行ログ
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div
            ref={terminalRef}
            className="bg-zinc-950 text-zinc-100 font-mono text-xs p-4 rounded h-96 overflow-y-auto"
          >
            {log.length === 0 ? (
              <div className="text-zinc-500">接続中...</div>
            ) : (
              log.map((line, i) => (
                <div key={i} className="whitespace-pre-wrap">
                  {line}
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
