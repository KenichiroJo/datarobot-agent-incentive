import { PATHS } from '@/constants/path.ts';
import { lazy } from 'react';
import { Navigate } from 'react-router-dom';
import { SettingsLayout } from './pages/SettingsLayout';
import { ChatPage } from './pages/ChatPage';
import { EmptyStatePage } from './pages/EmptyState.tsx';
import { MainLayout } from './pages/MainLayoutWithChatList';
import { DashboardPage } from './pages/commission/DashboardPage';
import { UploadPage } from './pages/commission/UploadPage';
import { CalculatePage } from './pages/commission/CalculatePage';
import { ReviewPage } from './pages/commission/ReviewPage';
import { ResultPage } from './pages/commission/ResultPage';

const OAuthCallback = lazy(() => import('./pages/OAuthCallback'));

export const appRoutes = [
  { path: PATHS.OAUTH_CB, element: <OAuthCallback /> },
  {
    element: <MainLayout />,
    children: [
      { path: PATHS.COMMISSION.DASHBOARD, element: <DashboardPage /> },
      { path: PATHS.COMMISSION.UPLOAD, element: <UploadPage /> },
      { path: PATHS.COMMISSION.CALCULATE, element: <CalculatePage /> },
      { path: PATHS.COMMISSION.REVIEW, element: <ReviewPage /> },
      { path: PATHS.COMMISSION.RESULT, element: <ResultPage /> },
      { path: PATHS.CHAT_EMPTY, element: <EmptyStatePage /> },
      { path: PATHS.CHAT, element: <ChatPage /> },
      {
        path: PATHS.SETTINGS.ROOT,
        element: <SettingsLayout />,
        children: [{ path: 'sources', element: <Navigate to={PATHS.SETTINGS.ROOT} replace /> }],
      },
      { path: '*', element: <Navigate to={PATHS.COMMISSION.DASHBOARD} replace /> },
    ],
  },
];
