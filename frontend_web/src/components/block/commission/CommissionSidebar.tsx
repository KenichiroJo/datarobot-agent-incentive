// コミッション計算ワークフロー用サイドバー
//
// 既存の ChatSidebar とは独立した、commission ページ群専用のナビゲーション。
// shadcn の Sidebar プリミティブを利用する。

import { useNavigate, useLocation, Link } from 'react-router-dom';
import {
  LayoutDashboard,
  Upload as UploadIcon,
  Calculator,
  Eye,
  BarChart3,
  MessageSquare,
  RotateCcw,
} from 'lucide-react';

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import { PATHS } from '@/constants/path';
import { useCommissionSession } from '@/store/commission-session-store';
import { useDashboard, useResetSession } from '@/api/commission/hooks';

interface NavItem {
  label: string;
  path: string;
  icon: typeof LayoutDashboard;
  badgeCount?: number;
}

export function CommissionSidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const sessionId = useCommissionSession((s) => s.sessionId);
  const resetLocal = useCommissionSession((s) => s.reset);
  const resetMutation = useResetSession();
  const dashboard = useDashboard(sessionId, Boolean(sessionId));
  const hitlPending = dashboard.data?.kpi.hitl_pending ?? 0;

  const items: NavItem[] = [
    { label: 'ダッシュボード', path: PATHS.COMMISSION.DASHBOARD, icon: LayoutDashboard },
    { label: 'ファイルアップロード', path: PATHS.COMMISSION.UPLOAD, icon: UploadIcon },
    { label: '計算実行', path: PATHS.COMMISSION.CALCULATE, icon: Calculator },
    {
      label: '差異レビュー',
      path: PATHS.COMMISSION.REVIEW,
      icon: Eye,
      badgeCount: hitlPending,
    },
    { label: '計算結果', path: PATHS.COMMISSION.RESULT, icon: BarChart3 },
    { label: 'AI チャット', path: PATHS.CHAT_EMPTY, icon: MessageSquare },
  ];

  const handleReset = async () => {
    if (sessionId) {
      try {
        await resetMutation.mutateAsync(sessionId);
      } catch {
        // バックエンド側のリセット失敗は無視 (UI 側は確実にクリア)
      }
    }
    resetLocal();
    navigate(PATHS.COMMISSION.DASHBOARD);
  };

  return (
    <Sidebar>
      <SidebarHeader>
        <div className="px-3 py-2">
          <div className="text-sm font-semibold">手数料計算エージェント</div>
          <div className="text-xs text-muted-foreground">DataRobot AI Workflow</div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => {
                const Icon = item.icon;
                const active = location.pathname.startsWith(item.path);
                return (
                  <SidebarMenuItem key={item.path}>
                    <SidebarMenuButton asChild isActive={active}>
                      <Link to={item.path}>
                        <Icon className="size-4" />
                        <span>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                    {item.badgeCount && item.badgeCount > 0 ? (
                      <SidebarMenuBadge>{item.badgeCount}</SidebarMenuBadge>
                    ) : null}
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <div className="border-t px-3 py-2 text-xs">
          <div className="text-muted-foreground">セッションID</div>
          <div className="truncate font-mono" title={sessionId ?? '未開始'}>
            {sessionId ? sessionId.slice(0, 14) + '…' : '未開始'}
          </div>
          <Button
            size="sm"
            variant="secondary"
            className="mt-2 w-full"
            onClick={handleReset}
            disabled={resetMutation.isPending}
          >
            <RotateCcw className="mr-1 size-3" />
            処理をリセット
          </Button>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
