import { LightbulbIcon } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

import { SidebarMenuButton, SidebarMenuItem } from '@/components/ui/sidebar';

import { useTutorialTour } from './useTutorialTour';

interface TutorialLauncherProps {
  /** Dashboard ルートのパス。ここを開いた時のみ初回自動起動する。 */
  autoStartPath?: string;
}

/**
 * サイドバー用の「使い方ガイド」ボタン + 初回訪問時の自動起動。
 *
 * - 初回マウント時に localStorage 完了フラグをチェックし、未完了なら
 *   `autoStartPath` に居る場合に自動でツアー開始する。
 * - ボタン押下時は localStorage を無視して再起動。
 */
export function TutorialLauncher({ autoStartPath = '/' }: TutorialLauncherProps) {
  const { startTour, hasCompletedTour } = useTutorialTour();
  const { pathname } = useLocation();
  const autoStartedRef = useRef(false);

  useEffect(() => {
    if (autoStartedRef.current) return;
    if (pathname !== autoStartPath) return;
    if (hasCompletedTour()) return;

    autoStartedRef.current = true;
    // ページ描画完了を待ってから開始
    const t = setTimeout(() => {
      startTour();
    }, 800);
    return () => clearTimeout(t);
  }, [pathname, autoStartPath, hasCompletedTour, startTour]);

  return (
    <SidebarMenuItem key="tutorial-launcher">
      <SidebarMenuButton onClick={() => startTour()}>
        <LightbulbIcon />
        <span>使い方ガイド</span>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}
