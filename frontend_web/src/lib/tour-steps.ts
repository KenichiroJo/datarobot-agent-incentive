import type { DriveStep } from 'driver.js';

/**
 * 5 ステップのチュートリアル定義。
 *
 * navigate を必要とするステップは TourStep.onNext で navigate キー経由で
 * useTutorialTour 側のコールバックを受け取る。ステップ定義自体は副作用なし。
 */
export interface TourStep extends DriveStep {
  /** このステップから次に進むときに遷移するパス */
  navigateTo?: string;
  /** target が存在しない場合に自動でスキップするか */
  skipIfMissing?: boolean;
}

export const TOUR_STEPS: TourStep[] = [
  {
    // Step 1: Welcome
    popover: {
      title: '販売管理手数料計算エージェントへようこそ',
      description:
        'AI エージェントが売上明細と取引条件マスタを突合して、代理店ごとの月次手数料を自動計算します。約 1 分で主要画面をご案内します。',
      side: 'over',
      align: 'center',
    },
  },
  {
    // Step 2: Dashboard KPI
    element: '[data-tour="dashboard-kpi"]',
    popover: {
      title: 'ダッシュボード KPI',
      description:
        'ここに総処理件数・自動完了率・HITL 対象・合計手数料の 4 指標が表示されます。計算実行後に自動更新されます。',
      side: 'bottom',
      align: 'start',
    },
    skipIfMissing: true,
  },
  {
    // Step 3: 新規計算ボタン (ページ遷移あり)
    element: '[data-tour="new-calc-button"]',
    popover: {
      title: '新規計算を開始',
      description:
        'ここから計算を開始します。「次へ」を押すとアップロード画面に自動遷移します。',
      side: 'left',
      align: 'center',
    },
    navigateTo: '/commission/upload',
    skipIfMissing: true,
  },
  {
    // Step 4: アップロードドロップゾーン
    element: '[data-tour="upload-zone-sales"]',
    popover: {
      title: 'ファイルアップロード',
      description:
        '売上明細 Excel と取引条件マスタ Excel をドラッグ&ドロップするか、クリックで選択します。ファイル名から自動で種別を判定します。',
      side: 'bottom',
      align: 'start',
    },
    skipIfMissing: true,
  },
  {
    // Step 5: 計算開始ボタン
    element: '[data-tour="calculate-start"]',
    popover: {
      title: '計算開始',
      description:
        '2 ファイル投入後にこのボタンが有効化します。クリックすると AI エージェントが SSE でリアルタイム進捗を配信し、異常レコードは HITL 対象として人間が確認できます。完了後、ResultPage で計算インサイトと Excel ダウンロードが利用可能です。これでチュートリアル完了です。',
      side: 'top',
      align: 'end',
    },
    skipIfMissing: true,
  },
];

export const TOUR_LOCALSTORAGE_KEY = 'commission_tour_completed_v1';
