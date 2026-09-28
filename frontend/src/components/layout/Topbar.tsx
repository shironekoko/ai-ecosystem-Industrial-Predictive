import React from 'react';
import { Cpu, Bell, Shield, User as UserIcon, PanelLeft, LogIn, LogOut, Lock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { UserRole } from '../../types';

interface TopbarProps {
  currentRole?: UserRole;
  onRoleChange?: (role: UserRole) => void;
  unreadCount: number;
  onToggleSidebar: () => void;
}

export const Topbar: React.FC<TopbarProps> = ({ unreadCount, onToggleSidebar }) => {
  const navigate = useNavigate();
  const { user, isAuthenticated, logout } = useAuth();

  return (
    <header className="h-14 border-b border-gray-200 bg-white sticky top-0 z-40 px-4 flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-2">
        {/* Sidebar Toggle */}
        <button
          onClick={onToggleSidebar}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 transition"
          title="Toggle Sidebar"
        >
          <PanelLeft className="w-4.5 h-4.5" />
        </button>

        {/* Logo */}
        <div className="flex items-center gap-2.5 cursor-pointer" onClick={() => navigate('/dashboard')}>
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-600 to-indigo-500 flex items-center justify-center shadow-sm">
            <Cpu className="w-4 h-4 text-white" />
          </div>
          <div className="hidden md:block">
            <span className="font-bold text-sm text-gray-900">Nonastreda CNC AI</span>
            <p className="text-[10px] text-indigo-600 font-semibold -mt-0.5">Milling Tool Wear PdM & Dual-AI QC</p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2.5">
        {/* Notifications */}
        <button
          onClick={() => navigate('/notifications')}
          className="relative p-2 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition"
          title="Notifications"
        >
          <Bell className="w-4.5 h-4.5" />
          {unreadCount > 0 && (
            <span className="absolute top-0.5 right-0.5 w-4 h-4 rounded-full bg-red-500 text-[10px] text-white flex items-center justify-center font-bold ring-2 ring-white">
              {unreadCount}
            </span>
          )}
        </button>

        {isAuthenticated && user ? (
          /* Logged In User State — Role is locked to the account */
          <>
            {/* Locked Role Badge (No manual switcher) */}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${
                user.role === 'admin'
                  ? 'bg-purple-50 text-purple-700 border-purple-200'
                  : 'bg-indigo-50 text-indigo-700 border-indigo-200'
              }`}
              title={`Role locked to ${user.title}`}
            >
              {user.role === 'admin' ? (
                <Shield className="w-3.5 h-3.5 text-purple-600" />
              ) : (
                <UserIcon className="w-3.5 h-3.5 text-indigo-600" />
              )}
              <span>{user.role === 'admin' ? 'Administrator' : 'Engineer'}</span>
            </div>

            {/* User Profile */}
            <div className="flex items-center gap-2 pl-2 border-l border-gray-200">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center font-semibold text-xs ${
                  user.role === 'admin'
                    ? 'bg-gradient-to-br from-purple-100 to-purple-200 text-purple-800'
                    : 'bg-gradient-to-br from-indigo-100 to-indigo-200 text-indigo-800'
                }`}
              >
                {user.name ? user.name.slice(0, 2).toUpperCase() : <UserIcon className="w-4 h-4" />}
              </div>
              <div className="hidden lg:block text-xs">
                <div className="font-semibold text-gray-800 leading-tight">{user.name}</div>
                <div className="text-[10px] text-gray-500">{user.title}</div>
              </div>

              {/* Logout Button */}
              <button
                onClick={logout}
                className="p-1.5 ml-1 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition"
                title="Sign Out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </>
        ) : (
          /* Guest / Unauthenticated State */
          <div className="flex items-center gap-2 pl-2 border-l border-gray-200">
            <span className="hidden sm:inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 text-[11px] font-medium">
              <Lock className="w-3 h-3" />
              Guest Mode
            </span>
            <button
              onClick={() => navigate('/login')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-sm transition"
            >
              <LogIn className="w-3.5 h-3.5" />
              <span>Sign In / Register</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
