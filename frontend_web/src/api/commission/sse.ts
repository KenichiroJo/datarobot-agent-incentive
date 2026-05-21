// POST + SSE consumer (EventSource は GET のみ対応のため fetch + ReadableStream で実装)

import { getApiUrl } from '@/lib/url-utils';
import type { CalculateRequest, CalculationStreamEvent } from './types';

export interface StreamCalculationOptions {
  payload: CalculateRequest;
  signal: AbortSignal;
  onEvent: (event: CalculationStreamEvent) => void;
  onError?: (err: Error) => void;
}

/**
 * POST /api/v1/commission/calculate を SSE フレーム単位で購読する。
 * apiClient (axios) は SSE 非対応のため、ここでは fetch を直接使う。
 */
export async function streamCalculation(opts: StreamCalculationOptions): Promise<void> {
  const url = `${getApiUrl()}/v1/commission/calculate`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(opts.payload),
    credentials: 'include',
    signal: opts.signal,
  });

  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => '');
    throw new Error(`SSE 接続失敗: HTTP ${res.status} ${text.slice(0, 200)}`);
  }

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      // SSE フレーム区切りは "\n\n"
      let idx: number;
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const parsed = parseSseFrame(frame);
        if (parsed) {
          opts.onEvent(parsed);
        }
      }
    }
  } catch (err) {
    if (opts.onError) opts.onError(err as Error);
    else throw err;
  }
}

function parseSseFrame(frame: string): CalculationStreamEvent | null {
  // ":heartbeat" コメント行などをスキップ
  const lines = frame.split('\n');
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (dataLines.length === 0) return null;
  try {
    return JSON.parse(dataLines.join('\n')) as CalculationStreamEvent;
  } catch {
    return null;
  }
}
