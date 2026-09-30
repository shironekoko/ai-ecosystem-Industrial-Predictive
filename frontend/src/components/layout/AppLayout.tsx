import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Topbar } from './Topbar';
import { Sidebar } from './Sidebar';
import { UserRole } from '../../types';

interface AppLayoutProps {
  currentRole: UserRole;
  onRoleChange: (role: UserRole) => void;
  retrainQueueCount: number;
  unreadAlertCount: number;
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  currentRole,
  onRoleChange,
  retrainQueueCount,
  unreadAlertCount,
}) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="h-screen flex flex-col bg-gray-50 text-gray-900 overflow-hidden">
      <Topbar
        currentRole={currentRole}
        onRoleChange={onRoleChange}
        unreadCount={unreadAlertCount}
        onToggleSidebar={() => setSidebarCollapsed((p) => !p)}
      />

      <div className="flex-1 flex overflow-hidden relative">
        <Sidebar
          collapsed={sidebarCollapsed}
          retrainQueueCount={retrainQueueCount}
          unreadAlertCount={unreadAlertCount}
        />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AppLayout;
