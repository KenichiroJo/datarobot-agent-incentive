export const PATHS = {
  HOME: '/',
  CHAT_EMPTY: '/chat',
  CHAT: '/chat/:chatId',
  OAUTH_CB: '/oauth/callback',
  SETTINGS: {
    ROOT: '/settings',
  },
  COMMISSION: {
    DASHBOARD: '/',
    UPLOAD: '/commission/upload',
    CALCULATE: '/commission/calculate/:sessionId',
    REVIEW: '/commission/review/:sessionId',
    RESULT: '/commission/result/:sessionId',
  },
} as const;
