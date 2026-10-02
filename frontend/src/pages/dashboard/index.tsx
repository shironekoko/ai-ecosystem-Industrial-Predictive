import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../services/api';
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
  progressPct?: number;
  flankWearUm: number | null;
  rulCuts: number | null;
  healthIndex: number;
  status: 'HEALTHY' | 'WARNING' | 'CRITICAL';
  feedRate: number;
  speedRpm: number;
}

export function Dashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [fleet, setFleet] = useState<SpindleFleetItem[]>([]);
  const [verifiedCount, setVerifiedCount] = useState<number>(0);

  useEffect(() => {
    let isMounted = true;

    const fetchDashboardData = () => {
      api.getFleetSpindles().then((data) => {
        if (isMounted && Array.isArray(data) && data.length > 0) {
          setFleet(data);
        }
      });
      api.getAuditLogs().then((res) => {
        if (isMounted && res && typeof res.total === 'number') {
          const confirmed = res.items
            ? res.items.filter((i: any) => i.eventType === 'WEAR_CONFIRMED' || i.eventType === 'FALSE_ALARM_FLAGGED' || i.eventType === 'RETRAIN_TRIGGERED').length
            : res.total;
          setVerifiedCount(confirmed || res.total);
        }
      });
    };

    fetchDashboardData();
    // 1.5s background polling ensures freshness even if websocket is reconnecting
    const interval = setInterval(fetchDashboardData, 1500);
    window.addEventListener('focus', fetchDashboardData);

    // Live Telemetry WebSocket: Streams physical milling progress and AI wear status directly
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl =
      (import.meta as any).env?.VITE_WS_URL ||
      `${wsProtocol}//${window.location.hostname}:8000/api/v1/telemetry/spindle/stream`;

    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(wsUrl);
      socket.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const packet = JSON.parse(event.data);
          if (packet && packet.passIndex !== undefined) {
            setFleet((prev) => {
              if (prev.length === 0) return prev;
              const isHalted = packet.interlockStatus === 'TRIPPED' || packet.machineState === 'EMERGENCY_HALTED';
              const isWarning = packet.inference?.condition === 'USED';
              const newStatus: 'HEALTHY' | 'WARNING' | 'CRITICAL' = isHalted ? 'CRITICAL' : (isWarning ? 'WARNING' : 'HEALTHY');

              return prev.map((sp) => {
                if (sp.id === 'CNC-SP-01' || sp.toolId === packet.toolId) {
                  return {
                    ...sp,
                    currentRun: Number(packet.passIndex),
                    progressPct: Number(packet.runProgressPct ?? 0),
                    status: newStatus,
                    healthIndex: newStatus === 'CRITICAL' ? 25 : (newStatus === 'WARNING' ? 70 : 98),
                  };
                }
                return sp;
              });
            });
          }
        } catch {}
      };
    } catch (e) {
      console.warn('[Dashboard] Telemetry WS connection warning:', e);
    }

    return () => {
      isMounted = false;
      clearInterval(interval);
      window.removeEventListener('focus', fetchDashboardData);
      if (socket) {
        socket.close();
      }
    };
  }, []);

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
          value={fleet.length > 0 ? `${fleet.length} Machine${fleet.length !== 1 ? 's' : ''}` : '0 Machines'}
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
          value={`${verifiedCount} Verified`}
          icon={CheckCircle2}
          accent="amber"
          trend="up"
          trendLabel="Active Learning Ready"
        />
      </div>

      {/* Fast Action Shortcuts */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <button
          onClick={() => navigate(`/machine-monitoring?tool=${fleet[0]?.toolId || 10}`)}
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
                      <div className="space-y-1.5 min-w-[130px]">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-semibold text-gray-800">
                            Pass #{spindle.currentRun}
                          </span>
                          <span className="text-gray-400 font-mono text-[10px]">
                            {spindle.status === 'CRITICAL'
                              ? 'Halted'
                              : spindle.progressPct != null
                              ? `${Math.round(spindle.progressPct)}%`
                              : 'Active'}
                          </span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                          <div
                            className={`h-full transition-all duration-300 rounded-full ${
                              spindle.status === 'CRITICAL'
                                ? 'bg-rose-500'
                                : spindle.status === 'WARNING'
                                ? 'bg-amber-400'
                                : 'bg-indigo-600'
                            }`}
                            style={{
                              width: `${
                                spindle.status === 'CRITICAL'
                                  ? 100
                                  : Math.max(5, Math.min(100, spindle.progressPct ?? 0))
                              }%`,
                            }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span className="font-semibold text-gray-600 font-mono">
                        {spindle.flankWearUm != null ? `${spindle.flankWearUm} µm` : '--'}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-gray-600 font-mono font-bold">
                      {spindle.rulCuts != null ? `${spindle.rulCuts} cuts left` : '--'}
                    </td>
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
                        onClick={() => navigate(`/machine-monitoring?machine=${spindle.id}&tool=${spindle.toolId}`)}
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
