import React from 'react';

interface StatusBadgeProps {
  status: 'connected' | 'disconnected' | 'pending' | 'healthy' | 'warning' | 'critical';
  label?: string;
  size?: 'sm' | 'md';
}

const statusConfig = {
  connected: { dot: 'bg-emerald-500', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', defaultLabel: 'Connected' },
  disconnected: { dot: 'bg-gray-400', bg: 'bg-gray-50', text: 'text-gray-500', border: 'border-gray-200', defaultLabel: 'Not Connected' },
  pending: { dot: 'bg-amber-500 animate-pulse', bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', defaultLabel: 'Pending' },
  healthy: { dot: 'bg-emerald-500', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', defaultLabel: 'Healthy' },
  warning: { dot: 'bg-amber-500', bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', defaultLabel: 'Warning' },
  critical: { dot: 'bg-red-500 animate-pulse', bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', defaultLabel: 'Critical' },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label, size = 'sm' }) => {
  const cfg = statusConfig[status];
  const isSmall = size === 'sm';

  return (
    <span className={`inline-flex items-center gap-1.5 ${isSmall ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'} rounded-full ${cfg.bg} ${cfg.text} border ${cfg.border} font-medium`}>
      <span className={`${isSmall ? 'w-1.5 h-1.5' : 'w-2 h-2'} rounded-full ${cfg.dot}`} />
      {label || cfg.defaultLabel}
    </span>
  );
};
