// コミッション計算のセッション状態を保持する Zustand store
//
// サーバー由来のデータ (records, summary) は React Query で管理し、
// クライアント側で必要な情報 (sessionId, 進行ステータス, uploadedFiles) のみここに置く。

import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';

import type { ProcessingStatus, UploadedFileInfo } from '@/api/commission/types';

export interface CommissionSessionState {
  sessionId: string | null;
  processingStatus: ProcessingStatus;
  uploadedFiles: {
    sales: UploadedFileInfo | null;
    master: UploadedFileInfo | null;
  };
  // セッション内 progress (Calculate 画面で更新する)
  progress: { current: number; total: number } | null;
  // Calculate 画面のターミナルログ
  logs: { ts: number; level: 'info' | 'warn' | 'error'; message: string }[];

  setSessionId: (id: string | null) => void;
  setProcessingStatus: (status: ProcessingStatus) => void;
  setUploadedFile: (kind: 'sales' | 'master', info: UploadedFileInfo | null) => void;
  setProgress: (p: { current: number; total: number } | null) => void;
  pushLog: (message: string, level?: 'info' | 'warn' | 'error') => void;
  clearLogs: () => void;
  reset: () => void;
}

const initial: Omit<
  CommissionSessionState,
  | 'setSessionId'
  | 'setProcessingStatus'
  | 'setUploadedFile'
  | 'setProgress'
  | 'pushLog'
  | 'clearLogs'
  | 'reset'
> = {
  sessionId: null,
  processingStatus: 'idle',
  uploadedFiles: { sales: null, master: null },
  progress: null,
  logs: [],
};

export const useCommissionSession = create<CommissionSessionState>()(
  immer((set) => ({
    ...initial,
    setSessionId: (id) =>
      set((s) => {
        s.sessionId = id;
      }),
    setProcessingStatus: (status) =>
      set((s) => {
        s.processingStatus = status;
      }),
    setUploadedFile: (kind, info) =>
      set((s) => {
        s.uploadedFiles[kind] = info;
      }),
    setProgress: (p) =>
      set((s) => {
        s.progress = p;
      }),
    pushLog: (message, level = 'info') =>
      set((s) => {
        s.logs.push({ ts: Date.now(), level, message });
        if (s.logs.length > 500) {
          s.logs.splice(0, s.logs.length - 500);
        }
      }),
    clearLogs: () =>
      set((s) => {
        s.logs = [];
      }),
    reset: () =>
      set((s) => {
        s.sessionId = initial.sessionId;
        s.processingStatus = initial.processingStatus;
        s.uploadedFiles = { sales: null, master: null };
        s.progress = null;
        s.logs = [];
      }),
  })),
);
