import { PATHS } from '@/constants/path.ts';
import { lazy } from 'react';
import { Navigate } from 'react-router-dom';
import { SettingsLayout } from './pages/SettingsLayout';
import { ChatPage } from './pages/ChatPage';
import { EmptyStatePage } from './pages/EmptyState.tsx';
import { MainLayout } from './pages/MainLayoutWithChatList';
import { CommissionLayout } from './pages/CommissionLayout';

const OAuthCallback = lazy(() => import('./pages/OAuthCallback'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const UploadPage = lazy(() => import('./pages/UploadPage'));
const CalculatePage = lazy(() => import('./pages/CalculatePage'));
const ReviewPage = lazy(() => import('./pages/ReviewPage'));
const ResultPage = lazy(() => import('./pages/ResultPage'));

export const appRoutes = [
  { path: PATHS.OAUTH_CB, element: <OAuthCallback /> },

  // 既存のチャット UI は維持 (MainLayoutWithChatList は ChatPage 専用)
  {
    element: <MainLayout />,
    children: [
      { path: PATHS.CHAT_EMPTY, element: <EmptyStatePage /> },
      { path: PATHS.CHAT, element: <ChatPage /> },
      {
        path: PATHS.SETTINGS.ROOT,
        element: <SettingsLayout />,
        children: [{ path: 'sources', element: <Navigate to={PATHS.SETTINGS.ROOT} replace /> }],
      },
    ],
  },

  // 新規: コミッション計算ワークフロー
  {
    element: <CommissionLayout />,
    children: [
      { path: PATHS.COMMISSION.DASHBOARD, element: <DashboardPage /> },
      { path: PATHS.COMMISSION.UPLOAD, element: <UploadPage /> },
      { path: PATHS.COMMISSION.CALCULATE, element: <CalculatePage /> },
      { path: PATHS.COMMISSION.REVIEW, element: <ReviewPage /> },
      { path: PATHS.COMMISSION.RESULT, element: <ResultPage /> },
    ],
  },

  // デフォルトは Dashboard
  { path: '/', element: <Navigate to={PATHS.COMMISSION.DASHBOARD} replace /> },
  { path: '*', element: <Navigate to={PATHS.COMMISSION.DASHBOARD} replace /> },
];
