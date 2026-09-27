import React from 'react';
import { useLocation } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

const routeLabels: Record<string, string> = {
  dashboard: 'Dashboard',
  login: 'Authentication',
  'machine-monitoring': 'Machine Monitoring',
  requisitions: 'Parts Requisitions',
  'visual-qc': 'Visual QC',
  inventory: 'Parts Catalog',
  'active-learning': 'Model Registry',
  'audit-log': 'Audit Trail',
  notifications: 'Notifications',
  'user-management': 'User Management',
  reports: 'Reports & Analytics',
};

export const PageHeader: React.FC<PageHeaderProps> = ({ title, subtitle, actions }) => {
  const location = useLocation();
  const segments = location.pathname.split('/').filter(Boolean);

  return (
    <div className="space-y-1 mb-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-xs text-gray-400">
        <Home className="w-3.5 h-3.5" />
        {segments.map((seg, i) => (
          <React.Fragment key={seg}>
            <ChevronRight className="w-3 h-3" />
            <span className={i === segments.length - 1 ? 'text-gray-600 font-medium' : ''}>
              {routeLabels[seg] || seg}
            </span>
          </React.Fragment>
        ))}
      </nav>

      {/* Title Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{title}</h1>
          {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  );
};
