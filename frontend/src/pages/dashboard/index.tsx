import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '../../components/common/PageHeader';
import { StatCard } from '../../components/common/StatCard';
import { StatusBadge } from '../../components/common/StatusBadge';
import { EmptyState } from '../../components/common/EmptyState';
import {
  Activity,
  ScanEye,
  AlertTriangle,
  CheckCircle2,
  Cpu,
  BrainCircuit,
  ArrowRight,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export interface SpindleFleetItem {
  id: string;
  name: string;
  toolId: number;
  currentRun: number;
  currentBlade: number;
  flankWearUm: number;
  rulCuts: number;
  healthIndex: number;
  status: 'HEALTHY' | 'WARNING' | 'CRITICAL';
  feedRate: number;
  speedRpm: number;
}

export function Dashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();

  // Fleet state - Initialized empty awaiting API connection
  const [fleet] = useState<SpindleFleetItem[]>([]);

  const criticalCount = fleet.filter((f) => f.status === 'CRITICAL').length;
  const warningCount = fleet.filter((f) => f.status === 'WARNING').length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Fleet Command Center"
        subtitle="Real-time CNC Spindle Tool Wear Telemetry & Dual-AI Diagnostics"
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge
              status={fleet.length > 0 ? 'connected' : 'disconnected'}
              label={fleet.length > 0 ? 'Telemetry: Active' : 'Telemetry: Standby'}
            />
            <span className="text-xs px-2.5 py-1 rounded-md bg-indigo-50 text-indigo-700 font-semibold border border-indigo-200">
              Edge AI Telemetry
            </span>
          </div>
        }
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <StatCard
          label="Active Spindles"
          value={fleet.length > 0 ? `${fleet.length} Machines` : '0 Machines'}
          icon={Cpu}
          accent="blue"
          trend="neutral"
          trendLabel={fleet.length > 0 ? 'Machines connected' : 'Awaiting edge agent'}
        />
        <StatCard
          label="Critical Wear Alarms"
          value={criticalCount}
          icon={AlertTriangle}
          accent="red"
          trend="neutral"
          trendLabel={`${warningCount} Warning Stages`}
        />
        <StatCard
          label="Human Confirmations"
          value="0 Verified"
          icon={CheckCircle2}
          accent="amber"
          trend="neutral"
          trendLabel="Active Learning Ready"
        />
      </div>

      {/* Fast Action Shortcuts */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <button
          onClick={() => navigate('/machine-monitoring')}
          className="group flex items-center p-4 bg-white border border-gray-200 rounded-xl shadow-sm hover:border-indigo-500 hover:shadow-md transition-all text-left"
        >
          <div className="bg-indigo-50 p-3 rounded-lg mr-4 group-hover:bg-indigo-600 transition-colors">
            <Activity className="w-6 h-6 text-indigo-600 group-hover:text-white transition-colors" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-gray-900 group-hover:text-indigo-600 transition-colors">
              Live Force Telemetry
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Pure Time-Series CRNN (TCN + BiGRU) stream on cutting forces (Fx, Fy, Fres)
            </p>
          </div>
          <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-indigo-600 group-hover:translate-x-1 transition-all" />
        </button>

        <button
          onClick={() => navigate('/visual-qc')}
          className="group flex items-center p-4 bg-white border border-gray-200 rounded-xl shadow-sm hover:border-emerald-500 hover:shadow-md transition-all text-left"
        >
          <div className="bg-emerald-50 p-3 rounded-lg mr-4 group-hover:bg-emerald-600 transition-colors">
            <ScanEye className="w-6 h-6 text-emerald-600 group-hover:text-white transition-colors" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-gray-900 group-hover:text-emerald-600 transition-colors">
              Dual-AI Tool Verification
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Microscope visual check & Human-in-the-Loop sign-off
            </p>
          </div>
          <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-emerald-600 group-hover:translate-x-1 transition-all" />
        </button>

        <button
          onClick={() => navigate('/active-learning')}
          className="group flex items-center p-4 bg-white border border-gray-200 rounded-xl shadow-sm hover:border-purple-500 hover:shadow-md transition-all text-left"
        >
          <div className="bg-purple-50 p-3 rounded-lg mr-4 group-hover:bg-purple-600 transition-colors">
            <BrainCircuit className="w-6 h-6 text-purple-600 group-hover:text-white transition-colors" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-gray-900 group-hover:text-purple-600 transition-colors">
              Model Registry & Retrain
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              MLflow tracking & background fine-tuning pipeline
            </p>
          </div>
          <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-purple-600 group-hover:translate-x-1 transition-all" />
        </button>
      </div>

      {/* Fleet Monitoring Matrix */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
          <div>
            <h3 className="font-bold text-gray-900 text-sm">CNC Spindle Fleet Status</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Monitoring cutting tool wear across connected machining centers
            </p>
          </div>
          <span className="text-xs text-gray-500 font-mono">Real-time Telemetry Matrix</span>
        </div>

        {fleet.length === 0 ? (
          <div className="py-14">
            <EmptyState
              icon={Cpu}
              title="No CNC Spindles Connected"
              description="Connected milling centers and real-time spindle tool wear metrics will appear here once telemetry edge agents connect to the API."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600">
              <thead className="bg-gray-50 text-[11px] uppercase tracking-wider text-gray-400 font-semibold border-b border-gray-100">
                <tr>
                  <th className="px-6 py-3">Machine / Spindle</th>
                  <th className="px-4 py-3">Tool ID</th>
                  <th className="px-4 py-3">Progression</th>
                  <th className="px-4 py-3">Flank Wear (Vb)</th>
                  <th className="px-4 py-3">RUL (Cuts)</th>
                  <th className="px-4 py-3">Condition Status</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 font-mono text-xs">
                {fleet.map((spindle) => (
                  <tr key={spindle.id} className="hover:bg-gray-50/70 transition-colors">
                    <td className="px-6 py-4 font-sans font-medium text-gray-900">
                      <div className="flex items-center gap-2">
                        <div
                          className={`w-2.5 h-2.5 rounded-full ${
                            spindle.status === 'CRITICAL'
                              ? 'bg-rose-500 animate-pulse'
                              : spindle.status === 'WARNING'
                              ? 'bg-amber-400'
                              : 'bg-emerald-400'
                          }`}
                        />
                        <span>{spindle.name}</span>
                      </div>
                      <span className="text-[11px] text-gray-400 font-mono ml-4.5">{spindle.id}</span>
                    </td>
                    <td className="px-4 py-4 font-bold text-gray-900">Tool #{spindle.toolId}</td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        <span className="text-gray-500 text-[11px]">Pass #{spindle.currentRun}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span className="font-semibold text-gray-900">{spindle.flankWearUm} µm</span>
                    </td>
                    <td className="px-4 py-4 text-gray-700 font-bold">{spindle.rulCuts} cuts left</td>
                    <td className="px-4 py-4 font-sans">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          spindle.status === 'CRITICAL'
                            ? 'bg-rose-100 text-rose-700 border border-rose-200'
                            : spindle.status === 'WARNING'
                            ? 'bg-amber-100 text-amber-800 border border-amber-200'
                            : 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                        }`}
                      >
                        {spindle.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right font-sans">
                      <button
                        onClick={() => navigate(`/machine-monitoring`)}
                        className="px-2.5 py-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 rounded transition"
                      >
                        Monitor
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export const DashboardPage = Dashboard;
export default Dashboard;
