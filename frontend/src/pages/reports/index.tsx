import React, { useState, useEffect } from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { StatCard } from '../../components/common/StatCard';
import { EmptyState } from '../../components/common/EmptyState';
import {
  Clock,
  BarChart3,
  Download,
  AlertTriangle,
  Layers,
  CheckCircle2,
  Cpu,
} from 'lucide-react';
import { api } from '../../services/api';

export function ReportsPage() {
  const [period, setPeriod] = useState<string>('30D');
  const [summary, setSummary] = useState<{
    totalInspections: number;
    confirmedWearCount: number;
    falseAlarmCount: number;
    falseAlarmRatePct: number;
    meanToolLifeCuts: number;
    activeSpindlesCount: number;
  } | null>(null);

  useEffect(() => {
    let isMounted = true;
    const fetchSummary = () => {
      api.getDegradationSummary(period).then((data) => {
        if (isMounted && data) {
          setSummary(data);
        }
      });
    };

    fetchSummary();
    const interval = setInterval(fetchSummary, 5000);
    window.addEventListener('focus', fetchSummary);

    return () => {
      isMounted = false;
      clearInterval(interval);
      window.removeEventListener('focus', fetchSummary);
    };
  }, [period]);

  const handleExportCsv = () => {
    window.open(`/api/v1/reports/export/csv?period=${encodeURIComponent(period)}`, '_blank');
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Tool Degradation & Quality Analytics Reports"
        subtitle="Milling tool lifecycle records · Human-in-the-Loop False Alarm analytics & verified wear history"
        actions={
          <div className="flex items-center gap-3">
            <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5 shadow-sm text-xs font-semibold">
              {['7D', '30D', '90D', 'All'].map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`px-3 py-1.5 rounded-md transition cursor-pointer ${
                    period === p ? 'bg-indigo-50 text-indigo-700 shadow-sm' : 'text-gray-500 hover:text-gray-900'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
            <button
              onClick={handleExportCsv}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold shadow-sm transition bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer active:scale-95"
            >
              <Download className="w-4 h-4" />
              <span>Export Audit Records (CSV)</span>
            </button>
          </div>
        }
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          label="Total Bench Inspections"
          value={summary ? `${summary.totalInspections} Audits` : '-- Audits'}
          icon={CheckCircle2}
          accent="blue"
          trend="neutral"
          trendLabel={summary ? `${summary.activeSpindlesCount} Active Spindles` : 'Awaiting data'}
        />
        <StatCard
          label="AI False Alarm Rate"
          value={summary ? `${summary.falseAlarmRatePct}%` : '-- %'}
          icon={AlertTriangle}
          accent="purple"
          trend="neutral"
          trendLabel={summary ? `${summary.falseAlarmCount} False Alarms Flagged` : 'Operator sign-offs'}
        />
        <StatCard
          label="Confirmed Wear Incidents"
          value={summary ? `${summary.confirmedWearCount} Incidents` : '-- Incidents'}
          icon={Layers}
          accent="red"
          trend="neutral"
          trendLabel="Fresh Tool Replacements"
        />
        <StatCard
          label="Mean Tool Life"
          value={summary && summary.meanToolLifeCuts > 0 ? `${summary.meanToolLifeCuts} Cuts` : '-- Cuts'}
          icon={Clock}
          accent="emerald"
          trend="neutral"
          trendLabel="Calculated from confirmed wear"
        />
      </div>

      {/* Main Reports Matrix or Empty State */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
          <div>
            <h3 className="font-bold text-gray-900 text-sm">Tool Wear Progression & Verification Analytics</h3>
            <p className="text-xs text-gray-500 mt-0.5">Historical verification records and AI prediction accuracy tracking</p>
          </div>
          <span className="text-xs font-mono text-gray-400">Period: {period}</span>
        </div>

        {!summary ? (
          <div className="py-16">
            <EmptyState
              icon={BarChart3}
              title="Awaiting Analytics Data"
              description="Connecting to backend report service to fetch lifecycle degradation and inspection statistics..."
            />
          </div>
        ) : (
          <div className="p-6 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-gray-50 rounded-xl border border-gray-100 space-y-2">
                <span className="text-xs font-bold text-gray-700 block uppercase tracking-wider">
                  Human-in-the-Loop Quality Control Summary
                </span>
                <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                  <div className="p-2.5 bg-white rounded-lg border border-gray-200">
                    <span className="text-[10px] text-gray-500 block">Total Sign-Offs</span>
                    <span className="text-sm font-bold text-indigo-700">{summary.totalInspections}</span>
                    <span className="text-[9px] text-gray-400 block">Logged to PostgreSQL</span>
                  </div>
                  <div className="p-2.5 bg-white rounded-lg border border-gray-200">
                    <span className="text-[10px] text-gray-500 block">Discrepancy (False Alarm)</span>
                    <span className="text-sm font-bold text-purple-700">{summary.falseAlarmCount}</span>
                    <span className="text-[9px] text-purple-600 block">Sent to Retrain Queue</span>
                  </div>
                </div>
              </div>

              <div className="p-4 bg-gray-50 rounded-xl border border-gray-100 space-y-2">
                <span className="text-xs font-bold text-gray-700 block uppercase tracking-wider">
                  Tooling Replacement & Spindle Fleet
                </span>
                <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                  <div className="p-2.5 bg-white rounded-lg border border-gray-200">
                    <span className="text-[10px] text-gray-500 block">Critical Wear Verified</span>
                    <span className="text-sm font-bold text-rose-700">{summary.confirmedWearCount}</span>
                    <span className="text-[9px] text-rose-600 block">Approved for replacement</span>
                  </div>
                  <div className="p-2.5 bg-white rounded-lg border border-gray-200">
                    <span className="text-[10px] text-gray-500 block">Average Runs to Dulled</span>
                    <span className="text-sm font-bold text-emerald-700">
                      {summary.meanToolLifeCuts > 0 ? `${summary.meanToolLifeCuts} Cuts` : '--'}
                    </span>
                    <span className="text-[9px] text-gray-400 block">Based on verified wear</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-gray-100 text-xs text-gray-500">
              <span>Data source: Nonastreda Multimodal Cutting Runs Dataset · PostgreSQL Audit Trail</span>
              <button
                onClick={handleExportCsv}
                className="text-xs font-bold text-indigo-600 hover:text-indigo-800 underline cursor-pointer"
              >
                Download Raw Audit Trail (CSV)
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ReportsPage;
