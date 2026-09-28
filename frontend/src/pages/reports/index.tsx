import React, { useState } from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { StatCard } from '../../components/common/StatCard';
import { EmptyState } from '../../components/common/EmptyState';
import {
  Clock,
  TrendingUp,
  BarChart3,
  Download,
  AlertTriangle,
  Layers,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export function ReportsPage() {
  const { isAuthenticated } = useAuth();
  const [period, setPeriod] = useState<string>('30D');

  // Reports data state - Initialized empty awaiting real analytics API
  const [reportRuns] = useState<any[]>([]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Tool Degradation & Reliability Reports"
        subtitle="Milling tool lifecycle analytics · ISO 8688 Flank Wear ($V_b$) Weibull reliability distributions"
        actions={
          <div className="flex items-center gap-3">
            <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5 shadow-sm text-xs font-semibold">
              {['7D', '30D', '90D', 'All'].map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`px-3 py-1.5 rounded-md transition ${
                    period === p ? 'bg-indigo-50 text-indigo-700 shadow-sm' : 'text-gray-500 hover:text-gray-900'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
            <button
              disabled={reportRuns.length === 0}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold shadow-sm transition ${
                reportRuns.length === 0
                  ? 'bg-gray-100 text-gray-400 border border-gray-200 cursor-not-allowed'
                  : 'bg-indigo-600 hover:bg-indigo-700 text-white'
              }`}
            >
              <Download className="w-4 h-4" />
              <span>Export PDF Report</span>
            </button>
          </div>
        }
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          label="Mean Tool Life (MTTF)"
          value="-- Cuts"
          icon={Clock}
          accent="blue"
          trend="neutral"
          trendLabel="Awaiting lifecycle data"
        />
        <StatCard
          label="Overall Machine OEE"
          value="-- %"
          icon={TrendingUp}
          accent="emerald"
          trend="neutral"
          trendLabel="Spindle utilization"
        />
        <StatCard
          label="AI False Alarm Rate"
          value="-- %"
          icon={AlertTriangle}
          accent="purple"
          trend="neutral"
          trendLabel="Awaiting inspector sign-offs"
        />
        <StatCard
          label="Mean Replace Time"
          value="-- min"
          icon={Layers}
          accent="amber"
          trend="neutral"
          trendLabel="Downtime benchmark"
        />
      </div>

      {/* Main Reports Matrix or Empty State */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
          <div>
            <h3 className="font-bold text-gray-900 text-sm">Tool Wear Progression Analytics</h3>
            <p className="text-xs text-gray-500 mt-0.5">Historical degradation curves and Weibull reliability models</p>
          </div>
          <span className="text-xs font-mono text-gray-400">Period: {period}</span>
        </div>

        {reportRuns.length === 0 ? (
          <div className="py-16">
            <EmptyState
              icon={BarChart3}
              title="No Degradation Reports Available"
              description="Tool wear curves, cutting force distributions, and Weibull survival models will be generated automatically once milling cycles are recorded in the database."
            />
          </div>
        ) : (
          <div className="p-6">
            {/* Real report visualization when data exists */}
          </div>
        )}
      </div>
    </div>
  );
}

export default ReportsPage;
