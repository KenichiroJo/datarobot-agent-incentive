import { useLayoutEffect } from 'react';
import { Outlet, useNavigate, useParams, useMatch, Link } from 'react-router-dom';
import { LayoutDashboardIcon, UploadIcon } from 'lucide-react';
import { ChatSidebar } from '@/components/block/chat/chat-sidebar';
import { useChatList } from '@/components/block/chat/hooks/use-chat-list';
import { MainLayoutProvider } from '@/components/block/chat/main-layout-context';
import { TutorialLauncher } from '@/components/tutorial/TutorialLauncher';
import {
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar';
import { PATHS } from '@/constants/path';

export function MainLayout() {
  const { chatId = '' } = useParams<{ chatId?: string }>();
  const navigate = useNavigate();

  const setChatIdHandler = (id: string) => {
    navigate(`/chat/${id}`);
  };

  const isChatEmptyPage = useMatch('/chat');
  const isChatSelectedPage = useMatch('/chat/:chatId');
  const isChat = isChatEmptyPage || isChatSelectedPage;

  const isDashboard = useMatch(PATHS.COMMISSION.DASHBOARD);
  const isUpload = useMatch(PATHS.COMMISSION.UPLOAD);

  const {
    hasChat,
    isNewChat,
    chats,
    isLoadingChats,
    addChatHandler,
    deleteChatHandler,
    isDeletingChat,
    refetchChats,
  } = useChatList({
    chatId,
    setChatId: setChatIdHandler,
    showStartChat: !chatId,
  });

  useLayoutEffect(() => {
    if (isLoadingChats || !chats || chats?.find(c => c.id === chatId)) {
      return;
    }
    if (!isChat) {
      return;
    }
    if (!chats.length) {
      addChatHandler();
    } else {
      setChatIdHandler(chats[0].id);
    }
  }, [chats, isLoadingChats, isChat, chatId]);

  const commissionMenu = (
    <>
      <SidebarMenuItem key="commission-dashboard">
        <SidebarMenuButton asChild isActive={!!isDashboard}>
          <Link to={PATHS.COMMISSION.DASHBOARD}>
            <LayoutDashboardIcon />
            <span>ダッシュボード</span>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
      <SidebarMenuItem key="commission-upload">
        <SidebarMenuButton asChild isActive={!!isUpload}>
          <Link to={PATHS.COMMISSION.UPLOAD}>
            <UploadIcon />
            <span>新規計算</span>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
      <TutorialLauncher autoStartPath={PATHS.COMMISSION.DASHBOARD} />
    </>
  );

  return (
    <div className="flex h-svh w-full flex-row">
      <ChatSidebar
        isLoading={isLoadingChats}
        chatId={chatId}
        chats={chats}
        onChatCreate={addChatHandler}
        onChatSelect={setChatIdHandler}
        onChatDelete={deleteChatHandler}
        isDeletingChat={isDeletingChat}
        topMenuitem={commissionMenu}
      />
      <MainLayoutProvider
        value={{
          hasChat,
          isNewChat,
          isLoadingChats,
          addChatHandler,
          refetchChats,
        }}
      >
        <Outlet />
      </MainLayoutProvider>
    </div>
  );
}
