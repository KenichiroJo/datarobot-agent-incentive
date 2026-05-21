// コミッション計算ワークフロー用レイアウト
//
// 既存の MainLayoutWithChatList は ChatPage 専用なので、commission ページ群には
// 独立した CommissionLayout を使う。

import { Outlet } from 'react-router-dom';

import { CommissionSidebar } from '@/components/block/commission/CommissionSidebar';
import { SidebarInset } from '@/components/ui/sidebar';

export function CommissionLayout() {
  return (
    <div className="flex h-svh w-full">
      <CommissionSidebar />
      <SidebarInset>
        <main className="flex h-full flex-col overflow-auto bg-[var(--commission-bg-base,#F8FAFC)]">
          <Outlet />
        </main>
      </SidebarInset>
    </div>
  );
}
