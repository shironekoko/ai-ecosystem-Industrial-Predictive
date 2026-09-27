import React, { useState } from 'react';
import {
  Activity,
  Thermometer,
  Gauge,
  Clock,
  Radio,
  Pause,
  Play,
  RotateCcw,
  Zap,
  Wind,
  Lock,
} from 'lucide-react';
import { PageHeader } from '../../components/common/PageHeader';
import { StatCard } from '../../components/common/StatCard';
import { StatusBadge } from '../../components/common/StatusBadge';
import { EmptyState } from '../../components/common/EmptyState';
import { useAuth } from '../../context/AuthContext';

/*
  C-MAPSS Turbofan Sensor Groups
  The test_FD001.txt has 26 columns:
  [engine_id, cycle, op1, op2, op3, s1..s21]
  
  Sensor groups:
  - Temperature: s2(T24 LPC outlet), s3(T30 HPC outlet), s4(T50 LPT outlet), s11(T2 fan inlet static)
  - Pressure: s6(P15 bypass duct), s7(P30 HPC outlet), s1(T2 fan inlet total - actually temp)
  - Speed: s8(Nf physical fan), s9(Nc physical core), s13(NRf corrected fan), s14(NRc corrected core)
  - Flow/Ratio: s5(P2 fan inlet), s10(epr), s12(phi fuel flow), s15(BPR bypass ratio)
  - Bleed: s17(htBleed enthalpy), s20(W31 HPT coolant), s21(W32 LPT coolant)
*/

type SensorGroup = 'temperature' | 'pressure' | 'speed' | 'flow' | 'bleed';

interface SensorGroupDef {
  key: SensorGroup;
  label: string;
  icon: React.FC<{ className?: string }>;
  sensors: { id: string; name: string; unit: string }[];
}

const sensorGroups: SensorGroupDef[] = [
  {
    key: 'temperature',
    label: 'Temperature',
    icon: Thermometer,
    sensors: [
      { id: 's2', name: 'T24 — LPC Outlet', unit: '°R' },
      { id: 's3', name: 'T30 — HPC Outlet', unit: '°R' },
      { id: 's4', name: 'T50 — LPT Outlet', unit: '°R' },
      { id: 's11', name: 'Ps30 — HPC Static', unit: 'psia' },
    ],
  },
  {
    key: 'pressure',
    label: 'Pressure',
    icon: Gauge,
    sensors: [
      { id: 's6', name: 'P15 — Bypass Duct Total', unit: 'psia' },
      { id: 's7', name: 'P30 — HPC Outlet Total', unit: 'psia' },
    ],
  },
  {
    key: 'speed',
    label: 'Shaft Speed',
    icon: Zap,
    sensors: [
      { id: 's8', name: 'Nf — Physical Fan Speed', unit: 'rpm' },
      { id: 's9', name: 'Nc — Physical Core Speed', unit: 'rpm' },
      { id: 's13', name: 'NRf — Corrected Fan Speed', unit: 'rpm' },
      { id: 's14', name: 'NRc — Corrected Core Speed', unit: 'rpm' },
    ],
  },
  {
    key: 'flow',
    label: 'Flow & Ratio',
    icon: Wind,
    sensors: [
      { id: 's10', name: 'epr — Engine Pressure Ratio', unit: '' },
      { id: 's12', name: 'phi — Fuel Flow / Ps30', unit: 'pps/psi' },
      { id: 's15', name: 'BPR — Bypass Ratio', unit: '' },
      { id: 's16', name: 'farB — Burner Fuel-Air Ratio', unit: '' },
    ],
  },
  {
    key: 'bleed',
    label: 'Bleed System',
    icon: Activity,
    sensors: [
      { id: 's17', name: 'htBleed — Bleed Enthalpy', unit: 'BTU/s' },
      { id: 's20', name: 'W31 — HPT Coolant Bleed', unit: 'lbm/s' },
      { id: 's21', name: 'W32 — LPT Coolant Bleed', unit: 'lbm/s' },
    ],
  },
];

export const MachineMonitoringPage: React.FC = () => {
  const [selectedEngine, setSelectedEngine] = useState<string>('');
  const [activeGroup, setActiveGroup] = useState<SensorGroup>('temperature');
  const [timeRange, setTimeRange] = useState<'1h' | '6h' | '24h' | '7d'>('24h');
  const [isStreaming, setIsStreaming] = useState(false);
  const { isAuthenticated } = useAuth();

  const currentGroup = sensorGroups.find((g) => g.key === activeGroup)!;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Machine Monitoring"
        subtitle="C-MAPSS Turbofan Engine — real-time sensor telemetry and RUL prognostics"
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge status={isStreaming ? 'connected' : 'disconnected'} label={isStreaming ? 'Streaming' : 'Idle'} />
            <button
              onClick={() => {
                if (!isAuthenticated) return;
                setIsStreaming((p) => !p);
              }}
              disabled={!isAuthenticated}
              title={!isAuthenticated ? 'Sign in required to stream sensor data' : ''}
              className={`px-3 py-2 rounded-lg text-xs font-medium flex items-center gap-1.5 transition shadow-sm ${
                !isAuthenticated
                  ? 'bg-gray-100 text-gray-400 border border-gray-200 cursor-not-allowed'
                  : isStreaming
                  ? 'bg-red-50 text-red-600 border border-red-200 hover:bg-red-100'
                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
              }`}
            >
              {!isAuthenticated ? (
                <>
                  <Lock className="w-3.5 h-3.5" />
                  <span>Sign In to Stream</span>
                </>
              ) : isStreaming ? (
                <>
                  <Pause className="w-3.5 h-3.5" />
                  <span>Pause Stream</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  <span>Start Stream</span>
                </>
              )}
            </button>
          </div>
        }
      />

      {/* Control Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 bg-white rounded-xl border border-gray-200 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-gray-400" />
            <span className="text-xs font-medium text-gray-500">Engine Unit:</span>
            <select
              value={selectedEngine}
              onChange={(e) => setSelectedEngine(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-gray-300 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white min-w-[180px]"
            >
              <option value="">Select engine...</option>
              {Array.from({ length: 100 }, (_, i) => (
                <option key={i + 1} value={String(i + 1)}>
                  Engine #{String(i + 1).padStart(3, '0')} (FD001)
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Time Range:</span>
          <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
            {(['1h', '6h', '24h', '7d'] as const).map((r) => (
              <button
                key={r}
                onClick={() => setTimeRange(r)}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition ${
                  timeRange === r ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {r.toUpperCase()}
              </button>
            ))}
          </div>
          <button className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition">
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Predicted RUL" value="--" unit="cycles" icon={Clock} accent="blue" />
        <StatCard label="Current Cycle" value="--" icon={Activity} accent="indigo" />
        <StatCard label="Op. Setting 1" value="--" icon={Gauge} accent="emerald" />
        <StatCard label="Health Status" value="--" icon={Zap} accent="amber" />
      </div>

      {/* Sensor Group Tabs */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
        {/* Tab Bar */}
        <div className="flex items-center gap-1 p-2 border-b border-gray-100 overflow-x-auto">
          {sensorGroups.map((group) => {
            const GIcon = group.icon;
            const isActive = activeGroup === group.key;
            return (
              <button
                key={group.key}
                onClick={() => setActiveGroup(group.key)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-600 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
              >
                <GIcon className="w-3.5 h-3.5" />
                {group.label}
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${isActive ? 'bg-indigo-100 text-indigo-600' : 'bg-gray-100 text-gray-400'}`}>
                  {group.sensors.length}
                </span>
              </button>
            );
          })}
        </div>

        {/* Sensor Charts Grid */}
        <div className="p-4">
          {!selectedEngine ? (
            <EmptyState
              icon={Radio}
              title="Select an engine unit to begin monitoring"
              description="Choose an engine from the dropdown above to view sensor telemetry data from the C-MAPSS test dataset."
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {currentGroup.sensors.map((sensor) => (
                <div key={sensor.id} className="border border-gray-100 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="text-xs font-semibold text-gray-700">{sensor.name}</p>
                      <p className="text-[10px] text-gray-400">{sensor.id.toUpperCase()} · {sensor.unit || 'dimensionless'}</p>
                    </div>
                    <span className="text-lg font-bold text-gray-300">--</span>
                  </div>
                  <div className="h-24 flex items-center justify-center border border-dashed border-gray-200 rounded bg-gray-50">
                    <p className="text-[10px] text-gray-400">Awaiting data stream</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* RUL Degradation Curve */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">RUL Degradation Curve</h2>
            <p className="text-xs text-gray-500">BiLSTM-predicted remaining useful life trend across operating cycles</p>
          </div>
          <div className="flex items-center gap-3 text-[10px]">
            <span className="flex items-center gap-1.5 text-indigo-500">
              <span className="w-3 h-0.5 rounded bg-indigo-500" /> Historical
            </span>
            <span className="flex items-center gap-1.5 text-cyan-500">
              <span className="w-3 h-0.5 rounded bg-cyan-400 border-b border-dashed" /> Forecast
            </span>
            <span className="flex items-center gap-1.5 text-red-400">
              <span className="w-3 h-0.5 rounded bg-red-400" /> Threshold
            </span>
          </div>
        </div>

        <div className="h-48 flex items-center justify-center border border-dashed border-gray-200 rounded-lg bg-gray-50">
          <EmptyState
            icon={Activity}
            title="No RUL prediction data"
            description="Start streaming sensor data to generate degradation forecasts from the BiLSTM engine."
          />
        </div>
      </div>
    </div>
  );
};

export default MachineMonitoringPage;
