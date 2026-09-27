import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Activity,
  ClipboardCheck,
  ScanEye,
  PackagePlus,
  BrainCircuit,
  History,
  Bell,
  Users,
  BarChart3,
  Shield,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface SidebarProps {
  collapsed: boolean;
  pendingReqCount: number;
  retrainQueueCount: number;
  unreadAlertCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  collapsed,
  pendingReqCount,
  retrainQueueCount,
  unreadAlertCount,
}) => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `w-full flex items-center ${collapsed ? 'justify-center' : 'justify-between'} px-3 py-2 rounded-lg text-[13px] font-medium transition group ${
      isActive
        ? 'bg-indigo-50 text-indigo-600 shadow-sm shadow-indigo-500/5'
        : 'text-gray-500 hover:text-gray-800 hover:bg-gray-50'
    }`;

  const NavItem = ({
    to,
    icon: Icon,
    label,
    badge,
  }: {
    to: string;
    icon: React.FC<{ className?: string }>;
    label: string;
    badge?: number;
  }) => (
    <NavLink to={to} className={navLinkClass}>
      <div className="flex items-center gap-2.5 min-w-0">
        <Icon className="w-4 h-4 shrink-0" />
        {!collapsed && <span className="truncate">{label}</span>}
      </div>
      {!collapsed && badge !== undefined && badge > 0 && (
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-100 text-red-600 font-semibold leading-none">
          {badge}
        </span>
      )}
    </NavLink>
  );

  const SectionLabel = ({ children }: { children: string }) =>
    collapsed ? (
      <div className="my-3 mx-2 border-t border-gray-100" />
    ) : (
      <div className="px-3 mb-1.5 mt-5 first:mt-0 text-[10px] font-bold tracking-widest text-gray-400 uppercase">
        {children}
      </div>
    );

  return (
    <aside
      className={`${
        collapsed ? 'w-16' : 'w-60'
      } border-r border-gray-200 bg-white flex flex-col shrink-0 select-none transition-all duration-200 ease-in-out`}
    >
      <div className="p-2 space-y-0.5 overflow-y-auto flex-1">
        <SectionLabel>Operations</SectionLabel>
        <NavItem to="/dashboard" icon={LayoutDashboard} label="Dashboard" />
        <NavItem to="/machine-monitoring" icon={Activity} label="Machine Monitoring" />
        <NavItem to="/requisitions" icon={ClipboardCheck} label="Requisitions" badge={pendingReqCount} />

        <SectionLabel>Quality Control</SectionLabel>
        <NavItem to="/visual-qc" icon={ScanEye} label="Inspection Console" />
        <NavItem to="/inventory" icon={PackagePlus} label="Parts Catalog" />
        <NavItem to="/active-learning" icon={BrainCircuit} label="Model Registry" badge={retrainQueueCount} />

        <SectionLabel>Governance</SectionLabel>
        <NavItem to="/audit-log" icon={History} label="Audit Trail" />
        <NavItem to="/notifications" icon={Bell} label="Notifications" badge={unreadAlertCount} />
        {/* Only visible to System Administrators */}
        {isAdmin && (
          <NavItem to="/user-management" icon={Users} label="Users & Roles" />
        )}
        <NavItem to="/reports" icon={BarChart3} label="Reports" />
      </div>

      {/* Footer Version */}
      {!collapsed && (
        <div className="p-3 border-t border-gray-100">
          <p className="text-[10px] text-gray-400 text-center">v0.1.0 · Pre-release</p>
        </div>
      )}
    </aside>
  );
};
