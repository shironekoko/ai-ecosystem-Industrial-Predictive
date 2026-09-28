import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Activity,
  ScanEye,
  BrainCircuit,
  History,
  Bell,
  Users,
  BarChart3,
  Cpu,
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
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-rose-100 text-rose-600 font-semibold leading-none">
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
        <SectionLabel>CNC Operations</SectionLabel>
        <NavItem to="/dashboard" icon={LayoutDashboard} label="Fleet Dashboard" />
        <NavItem to="/machine-monitoring" icon={Activity} label="Live Telemetry (1D-Forces)" />
        <NavItem to="/visual-qc" icon={ScanEye} label="Tool Verification (Dual-AI)" />

        <SectionLabel>MLOps & Governance</SectionLabel>
        <NavItem to="/notifications" icon={Bell} label="Alarm & Alerts" badge={unreadAlertCount} />
        <NavItem to="/active-learning" icon={BrainCircuit} label="Model Registry & MLOps" badge={retrainQueueCount} />
        <NavItem to="/audit-log" icon={History} label="Audit Trail" />
        <NavItem to="/reports" icon={BarChart3} label="Degradation Reports" />

        {/* Only visible to System Administrators */}
        {isAdmin && (
          <>
            <SectionLabel>System Admin</SectionLabel>
            <NavItem to="/user-management" icon={Users} label="Users & Access" />
          </>
        )}
      </div>

      {/* Footer Branding */}
      {!collapsed && (
        <div className="p-3 border-t border-gray-100 bg-gray-50/50">
          <div className="flex items-center gap-2">
            <Cpu className="w-3.5 h-3.5 text-indigo-500" />
            <p className="text-[11px] font-medium text-gray-600">Nonastreda CNC AI</p>
          </div>
          <p className="text-[10px] text-gray-400 mt-0.5">v2.0 · Predictive PdM</p>
        </div>
      )}
    </aside>
  );
};
