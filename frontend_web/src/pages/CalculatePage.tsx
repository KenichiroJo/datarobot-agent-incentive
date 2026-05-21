// 計算実行ページ: POST /api/v1/commission/calculate SSE を購読してログ + 進捗を表示

import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { streamCalculation } from '@/api/commission/sse';
import type { CalculationStreamEvent } from '@/api/commission/types';
import { StreamProgressBar } from '@/components/block/commission/StreamProgressBar';
import { TerminalLog } from '@/components/block/commission/TerminalLog';
import { Button } from '@/components/ui/button';
import { PATHS } from '@/constants/path';
import { useCommissionSession } from '@/store/commission-session-store';

type LogEntry = { ts: number; level: 'info' | 'warn' | 'error'; message: string };

export default function CalculatePage() {
  const navigate = useNavigate();
  const sessionId = useCommissionSession((s) => s.sessionId);
  const uploadedFiles = useCommissionSession((s) => s.uploadedFiles);
  const setProcessingStatus = useCommissionSession((s) => s.setProcessingStatus);

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [progress, setProgress] = useState<{ current: number; total: number }>({ current: 0, total: 0 });
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ hitlRequired: boolean; anomalyCount: number } | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const appendLog = (message: string, level: LogEntry['level'] = 'info') =>
    setLogs((prev) => [...prev, { ts: Date.now(), level, message }]);

  const start = async () => {
    if (!sessionId) {
      setError('セッション ID がありません。先にファイルをアップロードしてください。');
      return;
    }
    setLogs([]);
    setProgress({ current: 0, total: 0 });
    setError(null);
    setResult(null);
    setIsStreaming(true);
    setProcessingStatus('calculating');
    appendLog('SSE 接続を開始します…');

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamCalculation({
        payload: {
          session_id: sessionId,
          file_ids: [
            uploadedFiles.sales?.file_id,
            uploadedFiles.master?.file_id,
          ].filter(Boolean) as string[],
          options: { anomaly_threshold: 100_000, auto_approve_clean: true },
        },
        signal: controller.signal,
        onEvent: (e) => handleEvent(e),
        onError: (err) => {
          appendLog(`SSE エラー: ${err.message}`, 'error');
          setError(err.message);
        },
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'unknown error';
      appendLog(`接続エラー: ${msg}`, 'error');
      setError(msg);
    } finally {
      setIsStreaming(false);
    }
  };

  const handleEvent = (event: CalculationStreamEvent) => {
    switch (event.type) {
      case 'status': {
        const msg = event.message ?? '';
        const tag = event.node ? `[${event.node}]` : '[status]';
        appendLog(`${tag} ${msg || event.status || ''}`);
        if (event.status === 'awaiting_hitl') {
          appendLog(`HITL 承認待ち: ${event.pending_count ?? 0} 件`, 'warn');
        }
        break;
      }
      case 'progress':
        setProgress({ current: event.current, total: event.total });
        appendLog(`進捗: ${event.current} / ${event.total} 件`);
        break;
      case 'result': {
        if (event.delta) {
          appendLog(`[explainer] ${event.delta}`);
        }
        if (event.data) {
          const anomaly = event.data.anomaly_count ?? 0;
          const hitl = Boolean(event.data.hitl_required);
          appendLog(`結果: 異常 ${anomaly} 件 / HITL 要否 ${hitl ? 'あり' : 'なし'}`, hitl ? 'warn' : 'info');
          setResult({ hitlRequired: hitl, anomalyCount: anomaly });
        }
        break;
      }
      case 'error':
        appendLog(`サーバーエラー: ${event.message}`, 'error');
        setError(event.message);
        break;
      case 'done':
        appendLog(`完了 (理由: ${event.reason ?? 'completed'})`);
        setProcessingStatus(event.reason === 'hitl_required' ? 'awaiting_hitl' : 'done');
        // 完了後に自動遷移
        setTimeout(() => {
          if (event.reason === 'hitl_required') {
            navigate(PATHS.COMMISSION.REVIEW);
          } else {
            navigate(PATHS.COMMISSION.RESULT);
          }
        }, 800);
        break;
    }
  };

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-bold text-[var(--commission-text-primary)]">計算実行</h1>
        <p className="text-sm text-[var(--commission-text-muted)]">
          売上明細にマスタを突合して手数料を計算します。進捗はリアルタイムで表示されます。
        </p>
      </header>

      <div className="flex items-center gap-3">
        <Button onClick={start} disabled={isStreaming || !sessionId}>
          {isStreaming ? '実行中…' : '計算を開始する'}
        </Button>
        {result?.hitlRequired ? (
          <Button variant="secondary" onClick={() => navigate(PATHS.COMMISSION.REVIEW)}>
            差異レビューへ
          </Button>
        ) : null}
        {result && !result.hitlRequired ? (
          <Button variant="secondary" onClick={() => navigate(PATHS.COMMISSION.RESULT)}>
            計算結果を見る
          </Button>
        ) : null}
        {error ? (
          <span className="text-sm text-[var(--commission-danger)]">{error}</span>
        ) : null}
      </div>

      <StreamProgressBar current={progress.current} total={progress.total} label="計算進捗" />

      <TerminalLog entries={logs} />
    </div>
  );
}
