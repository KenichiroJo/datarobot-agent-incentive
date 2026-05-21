import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';

import type { HitlAction } from '@/api/commission/types';

interface RowDecision {
  action: HitlAction;
  manual_amount?: number;
  note?: string;
}

interface CommissionStoreState {
  currentSessionId: string | null;
  uploadedFilenames: string[];
  /** SSE で受信した進捗ログ */
  progressLog: string[];
  /** HITL レビュー画面で行ごとの決定を保持 */
  decisions: Record<number, RowDecision>;
  /** チェックボックスで選択中の record_no */
  selectedRecords: number[];
  setSession: (id: string) => void;
  setFilenames: (names: string[]) => void;
  appendLog: (line: string) => void;
  clearLog: () => void;
  setDecision: (recordNo: number, decision: RowDecision) => void;
  clearDecisions: () => void;
  toggleSelected: (recordNo: number) => void;
  selectAll: (records: number[]) => void;
  deselectAll: () => void;
  reset: () => void;
}

export const useCommissionStore = create<CommissionStoreState>()(
  immer((set) => ({
    currentSessionId: null,
    uploadedFilenames: [],
    progressLog: [],
    decisions: {},
    selectedRecords: [],

    setSession: (id) =>
      set((s) => {
        s.currentSessionId = id;
      }),
    setFilenames: (names) =>
      set((s) => {
        s.uploadedFilenames = names;
      }),
    appendLog: (line) =>
      set((s) => {
        s.progressLog.push(line);
      }),
    clearLog: () =>
      set((s) => {
        s.progressLog = [];
      }),
    setDecision: (recordNo, decision) =>
      set((s) => {
        s.decisions[recordNo] = decision;
      }),
    clearDecisions: () =>
      set((s) => {
        s.decisions = {};
      }),
    toggleSelected: (recordNo) =>
      set((s) => {
        const i = s.selectedRecords.indexOf(recordNo);
        if (i >= 0) s.selectedRecords.splice(i, 1);
        else s.selectedRecords.push(recordNo);
      }),
    selectAll: (records) =>
      set((s) => {
        s.selectedRecords = [...records];
      }),
    deselectAll: () =>
      set((s) => {
        s.selectedRecords = [];
      }),
    reset: () =>
      set((s) => {
        s.currentSessionId = null;
        s.uploadedFilenames = [];
        s.progressLog = [];
        s.decisions = {};
        s.selectedRecords = [];
      }),
  }))
);
