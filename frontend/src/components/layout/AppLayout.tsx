import React, { useState } from 'react';
import { Outlet, Link } from 'react-router-dom';
import { Topbar } from './Topbar';
import { Sidebar } from './Sidebar';
import { useAuth } from '../../context/AuthContext';
import { UserRole } from '../../types';
import { ShieldAlert, ArrowRight } from 'lucide-react';

interface AppLayoutProps {
  currentRole: UserRole;
  onRoleChange: (role: UserRole) => void;
  pendingReqCount: number;
  retrainQueueCount: number;
  unreadAlertCount: number;
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  currentRole,
  onRoleChange,
  pendingReqCount,
  retrainQueueCount,
  unreadAlertCount,
}) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 text-gray-900">
      <Topbar
        currentRole={currentRole}
        onRoleChange={onRoleChange}
        unreadCount={unreadAlertCount}
        onToggleSidebar={() => setSidebarCollapsed((p) => !p)}
      />

      {/* Guest Mode Banner */}
      {!isAuthenticated && (
        <div className="bg-amber-50/90 border-b border-amber-200/80 px-4 py-2 text-xs text-amber-900 flex flex-wrap items-center justify-between gap-2 shadow-xs">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              <strong>Guest Read-Only Mode:</strong> Action buttons, sensor streaming, and approval workflows are locked. Sign in or register to unlock full operational control.
            </span>
          </div>
          <Link
            to="/login"
            className="inline-flex items-center gap-1 px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded font-medium transition text-xs shrink-0"
          >
            <span>Sign In / Register</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          collapsed={sidebarCollapsed}
          pendingReqCount={pendingReqCount}
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
