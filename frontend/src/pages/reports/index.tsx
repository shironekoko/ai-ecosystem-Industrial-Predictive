import React, { useState, useEffect } from 'react';
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
import { api } from '../../services/api';

export function ReportsPage() {
  const { isAuthenticated } = useAuth();
  const [period, setPeriod] = useState<string>('30D');
  const [summary, setSummary] = useState<{
    meanToolLifeCuts: number;
    overallMachineOeePct: number;
    falseAlarmRatePct: number;
    meanReplaceTimeMin: number;
    weibullBeta: number;
    weibullEtaCuts: number;
  } | null>(null);

  useEffect(() => {
    api.getDegradationSummary(period).then((data) => {
      if (data) {
        setSummary(data);
      }
    });
  }, [period]);

  const handleExportPdf = () => {
    window.open(`/api/v1/reports/export/pdf?period=${encodeURIComponent(period)}`, '_blank');
  };

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
              onClick={handleExportPdf}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold shadow-sm transition bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer active:scale-95"
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
          value={summary ? `${summary.meanToolLifeCuts} Cuts` : '-- Cuts'}
          icon={Clock}
          accent="blue"
          trend="neutral"
          trendLabel={summary ? `Weibull η: ${summary.weibullEtaCuts}` : 'Awaiting data'}
        />
        <StatCard
          label="Overall Machine OEE"
          value={summary ? `${summary.overallMachineOeePct}%` : '-- %'}
          icon={TrendingUp}
          accent="emerald"
          trend="neutral"
          trendLabel="Spindle utilization"
        />
        <StatCard
          label="AI False Alarm Rate"
          value={summary ? `${summary.falseAlarmRatePct}%` : '-- %'}
          icon={AlertTriangle}
          accent="purple"
          trend="neutral"
          trendLabel="Operator sign-offs"
        />
        <StatCard
          label="Mean Replace Time"
          value={summary ? `${summary.meanReplaceTimeMin} min` : '-- min'}
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

        {!summary ? (
          <div className="py-16">
            <EmptyState
              icon={BarChart3}
              title="Awaiting Degradation Analytics"
              description="Connecting to backend report service to fetch Weibull degradation distributions..."
            />
          </div>
        ) : (
          <div className="p-6 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-gray-50 rounded-xl border border-gray-100 space-y-2">
                <span className="text-xs font-bold text-gray-700 block uppercase tracking-wider">
                  Weibull Reliability Distribution Parameters
                </span>
                <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                  <div className="p-2.5 bg-white rounded-lg border border-gray-200">
                    <span className="text-[10px] text-gray-500 block">Shape Parameter (β)</span>
                    <span className="text-sm font-bold text-indigo-700">{summary.weibullBeta}</span>
                    <span className="text-[9px] text-gray-400 block">(Wear-out failure regime)</span>
                  </div>
                  <div className="p-2.5 bg-white rounded-lg border border-gray-200">
                    <span className="text-[10px] text-gray-500 block">Scale Parameter (η)</span>
                    <span className="text-sm font-bold text-emerald-700">{summary.weibullEtaCuts} Cuts</span>
                    <span className="text-[9px] text-gray-400 block">(Characteristic tool life)</span>
                  </div>
                </div>
              </div>

              <div className="p-4 bg-gray-50 rounded-xl border border-gray-100 space-y-2">
                <span className="text-xs font-bold text-gray-700 block uppercase tracking-wider">
                  Operational Equipment Efficiency (OEE) & Maintenance
                </span>
                <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                  <div className="p-2.5 bg-white rounded-lg border border-gray-200">
                    <span className="text-[10px] text-gray-500 block">Spindle Availability (OEE)</span>
                    <span className="text-sm font-bold text-indigo-700">{summary.overallMachineOeePct}%</span>
                    <span className="text-[9px] text-emerald-600 block">Nominal performance</span>
                  </div>
                  <div className="p-2.5 bg-white rounded-lg border border-gray-200">
                    <span className="text-[10px] text-gray-500 block">Mean Replacement Time</span>
                    <span className="text-sm font-bold text-amber-700">{summary.meanReplaceTimeMin} min</span>
                    <span className="text-[9px] text-gray-400 block">Quick-change chuck</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-gray-100 text-xs text-gray-500">
              <span>Data source: Nonastreda Multimodal Cutting Runs Dataset · ISO 8688-2</span>
              <a
                href={`/api/v1/reports/export/csv?period=${encodeURIComponent(period)}`}
                className="text-xs font-bold text-indigo-600 hover:text-indigo-800 underline"
                target="_blank"
                rel="noreferrer"
              >
                Download Raw Metrics (CSV)
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ReportsPage;
