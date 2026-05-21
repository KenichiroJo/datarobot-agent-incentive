export const PATHS = {
  // 既存ルート (チャット系) — 触らない
  CHAT_EMPTY: '/chat',
  CHAT: '/chat/:chatId',
  OAUTH_CB: '/oauth/callback',
  SETTINGS: {
    ROOT: '/settings',
  },

  // コミッション計算ワークフロー (新規)
  COMMISSION: {
    DASHBOARD: '/dashboard',
    UPLOAD: '/upload',
    CALCULATE: '/calculate',
    REVIEW: '/review',
    RESULT: '/result',
  },
} as const;
