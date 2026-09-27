import React from 'react';
import { LucideIcon, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface StatCardProps {
  label: string;
  value: string | number;
  unit?: string;
  icon: LucideIcon;
  iconColor?: string;
  iconBg?: string;
  trend?: 'up' | 'down' | 'neutral';
  trendLabel?: string;
  accent?: 'blue' | 'red' | 'amber' | 'emerald' | 'purple' | 'indigo';
}

const accentMap = {
  blue: { bg: 'bg-blue-50', text: 'text-blue-600' },
  red: { bg: 'bg-red-50', text: 'text-red-500' },
  amber: { bg: 'bg-amber-50', text: 'text-amber-600' },
  emerald: { bg: 'bg-emerald-50', text: 'text-emerald-600' },
  purple: { bg: 'bg-purple-50', text: 'text-purple-600' },
  indigo: { bg: 'bg-indigo-50', text: 'text-indigo-600' },
};

const trendConfig = {
  up: { icon: TrendingUp, color: 'text-emerald-600' },
  down: { icon: TrendingDown, color: 'text-red-500' },
  neutral: { icon: Minus, color: 'text-gray-400' },
};

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  unit,
  icon: Icon,
  accent = 'blue',
  trend,
  trendLabel,
}) => {
  const a = accentMap[accent];
  const TrendIcon = trend ? trendConfig[trend].icon : null;
  const trendColor = trend ? trendConfig[trend].color : '';

  return (
    <div className="p-5 bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-gray-500">{label}</span>
        <div className={`w-9 h-9 rounded-lg ${a.bg} ${a.text} flex items-center justify-center`}>
          <Icon className="w-[18px] h-[18px]" />
        </div>
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-2xl font-bold text-gray-900">{value}</span>
        {unit && <span className="text-sm text-gray-400 font-medium">{unit}</span>}
      </div>
      {(trend || trendLabel) && (
        <div className={`mt-2 flex items-center gap-1 text-xs font-medium ${trendColor}`}>
          {TrendIcon && <TrendIcon className="w-3.5 h-3.5" />}
          <span>{trendLabel}</span>
        </div>
      )}
    </div>
  );
};
