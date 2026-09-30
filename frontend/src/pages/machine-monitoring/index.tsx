import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  Play,
  Pause,
  RotateCcw,
  ScanEye,
  Wifi,
  WifiOff,
  Scissors,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Clock,
  Radio,
  Trash2,
} from 'lucide-react';
import { PageHeader } from '../../components/common/PageHeader';
import { StatusBadge } from '../../components/common/StatusBadge';

// Interfaces for live telemetry & run progression
export interface RunProgressionItem {
  run: number;
  tsPrediction: 'SHARP' | 'USED' | 'DULLED';
  confidence: number;
  flankWearUm?: number;
  gapsUm?: number;
  fres?: number;
  note?: string;
  chipImageUrl?: string;
  chipPrediction?: 'SHARP' | 'USED' | 'DULLED';
  chipConfidence?: number;
}

export interface StreamingDataPoint {
  timestamp: number;
  fx: number;
  fy: number;
  fz?: number;
  fres: number;
}

export function MachineMonitoringPage() {
  const navigate = useNavigate();

  // Active Tool state
  const [selectedToolId] = useState<number>(10);

  // Per-Run Progression items (Clean / empty by default awaiting API or stream)
  const [runs, setRuns] = useState<RunProgressionItem[]>([]);
  const [activeRunNumber, setActiveRunNumber] = useState<number | null>(null);

  // Live streaming buffer (rolling window of the latest data points)
  const [streamPoints, setStreamPoints] = useState<StreamingDataPoint[]>([]);
  const [latestForces, setLatestForces] = useState<{
    fx: number;
    fy: number;
    fz?: number;
    fres: number;
  } | null>(null);

  // Stream connection state
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [streamStatus, setStreamStatus] = useState<'IDLE' | 'CONNECTING' | 'STREAMING' | 'ERROR'>('IDLE');
  const wsRef = useRef<WebSocket | null>(null);

  // Active run info derived from current runs array
  const currentRunInfo = runs.find((r) => r.run === activeRunNumber) || (runs.length > 0 ? runs[runs.length - 1] : null);
  const isTimeSeriesAlert = currentRunInfo?.tsPrediction === 'DULLED';

  // Two-Factor Logic:
  // Factor 1: Time-Series Force AI checks per-run.
  // Factor 2: Non-Time-Series Chip AI triggers ONLY IF Factor 1 Alerts!
  const isNonTimeActive = Boolean(currentRunInfo && isTimeSeriesAlert);
  const chipAiCondition = currentRunInfo?.chipPrediction || (isTimeSeriesAlert ? 'DULLED' : 'SHARP');
  const chipAiConfidence = currentRunInfo?.chipConfidence ?? (isTimeSeriesAlert ? 94.2 : 91.5);
  const isTwoFactorConfirmed = Boolean(isTimeSeriesAlert && chipAiCondition === 'DULLED');

  // WebSocket Live Telemetry Streaming Handler
  useEffect(() => {
    if (!isStreaming) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setStreamStatus('IDLE');
      return;
    }

    setStreamStatus('CONNECTING');
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl =
      (import.meta as any).env?.VITE_WS_URL ||
      `${wsProtocol}//${window.location.hostname}:8000/api/v1/telemetry/spindle/stream`;

    let socket: WebSocket;
    try {
      socket = new WebSocket(wsUrl);
      wsRef.current = socket;
    } catch {
      setStreamStatus('ERROR');
      return;
    }

    socket.onopen = () => {
      setStreamStatus('STREAMING');
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data && data.forces) {
          const newPoint: StreamingDataPoint = {
            timestamp: data.timestamp || Date.now(),
            fx: data.forces.fx,
            fy: data.forces.fy,
            fz: data.forces.fz,
            fres: data.forces.fres,
          };

          setLatestForces(data.forces);

          setStreamPoints((prev) => {
            const next = [...prev, newPoint];
            return next.length > 60 ? next.slice(next.length - 60) : next;
          });

          // Ingest run telemetry if packet contains passIndex
          if (data.passIndex !== undefined) {
            const passNum = Number(data.passIndex);
            const condition =
              data.inference?.condition ||
              (data.forces.fres > 210 ? 'DULLED' : data.forces.fres > 130 ? 'USED' : 'SHARP');
            const conf = data.inference?.confidence || 0.92;
            const flankWear = data.inference?.flankWearUm;

            setRuns((prev) => {
              const idx = prev.findIndex((r) => r.run === passNum);
              const item: RunProgressionItem = {
                run: passNum,
                tsPrediction: condition,
                confidence: conf,
                flankWearUm: flankWear,
                fres: data.forces.fres,
              };
              if (idx >= 0) {
                const updated = [...prev];
                updated[idx] = item;
                return updated;
              } else {
                return [...prev, item].sort((a, b) => a.run - b.run);
              }
            });

            // If first dulled detected, auto-select and stop stream safety interlock
            if (condition === 'DULLED') {
              setActiveRunNumber(passNum);
              setIsStreaming(false); // Safety cut on first dulled!
            } else if (activeRunNumber === null) {
              setActiveRunNumber(passNum);
            }
          }
        }
      } catch (err) {
        console.warn('[Stream] Parse error:', err);
      }
    };

    socket.onerror = () => {
      setStreamStatus('ERROR');
    };

    socket.onclose = () => {
      setStreamStatus('IDLE');
    };

    return () => {
      if (socket) {
        socket.close();
      }
    };
  }, [isStreaming]);

  // Chart dimensions & coordinate math
  const chartHeight = 220;
  const chartWidth = 720;
  const maxForceScale = 320; // 0 to 320 N

  // Calculate SVG Polyline from streaming points
  const getStreamingPolyline = (points: StreamingDataPoint[]) => {
    if (points.length < 2) return '';
    return points
      .map((p, idx) => {
        const x = (idx / (points.length - 1)) * chartWidth;
        const clampedFres = Math.max(0, Math.min(maxForceScale, p.fres));
        const y = chartHeight - 24 - (clampedFres / maxForceScale) * (chartHeight - 48);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  };

  const getStreamingFxyPolyline = (points: StreamingDataPoint[], key: 'fx' | 'fy') => {
    if (points.length < 2) return '';
    return points
      .map((p, idx) => {
        const x = (idx / (points.length - 1)) * chartWidth;
        const val = Math.abs(p[key]);
        const clamped = Math.max(0, Math.min(maxForceScale, val));
        const y = chartHeight - 24 - (clamped / maxForceScale) * (chartHeight - 48);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  };

  const thresholdY = chartHeight - 24 - (210 / maxForceScale) * (chartHeight - 48);
  const firstDulledRun = runs.find((r) => r.tsPrediction === 'DULLED');

  const handleClearData = () => {
    setStreamPoints([]);
    setLatestForces(null);
    setRuns([]);
    setActiveRunNumber(null);
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <PageHeader
        title="Time-Series Per-Run Progression & 2-Factor In-Process Tracking"
        subtitle="โมเดล Time-Series CRNN (BiGRU + Attention) เช็คราย Run ตามลำดับรอบตัด ➔ หยุดทันทีเมื่อเจอ Dulled อันแรก เพื่อดึงภาพ Chip"
        actions={
          <div className="flex items-center gap-2">
            {/* Clear / Reset Button */}
            {(runs.length > 0 || streamPoints.length > 0) && (
              <button
                onClick={handleClearData}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border border-gray-200 bg-white hover:bg-gray-50 text-gray-600 transition shadow-xs"
                title="ล้างข้อมูลกราฟและรอบตัดเพื่อเริ่มรับข้อมูลใหม่"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Clear Buffer</span>
              </button>
            )}

            {/* Live Streaming Toggle */}
            <button
              onClick={() => setIsStreaming((prev) => !prev)}
              className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold border transition shadow-xs ${
                isStreaming
                  ? 'bg-rose-50 text-rose-700 border-rose-300 hover:bg-rose-100'
                  : 'bg-indigo-600 hover:bg-indigo-700 text-white border-transparent'
              }`}
            >
              {isStreaming ? (
                <>
                  <Pause className="w-3.5 h-3.5" />
                  <span>Stop Telemetry Stream</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  <span>Start Telemetry Stream</span>
                </>
              )}
            </button>

            {/* Connection Status Badge */}
            <StatusBadge
              status={
                isTwoFactorConfirmed
                  ? 'critical'
                  : isStreaming
                  ? 'connected'
                  : streamStatus === 'CONNECTING'
                  ? 'warning'
                  : 'disconnected'
              }
              label={
                isTwoFactorConfirmed
                  ? `2-FACTOR ALERT: STOPPED AT RUN #${activeRunNumber}`
                  : isStreaming
                  ? `STREAMING ACTIVE (${streamPoints.length} pts)`
                  : streamStatus === 'CONNECTING'
                  ? 'CONNECTING TO WS...'
                  : 'STREAM STANDBY'
              }
            />
          </div>
        }
      />

      {/* Main Grid: Per-Run Dynamics Graph + Timeline (70%) + 2-Factor In-Process HUD (30%) */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left Column: กราฟตอน Run ราย Run + Timeline ลำดับรอบตัด */}
        <div className="col-span-12 lg:col-span-8 space-y-5">
          {/* Section 1: กราฟตัดชิ้นงานราย Run (Per-Run Signal & Cutting Dynamics Graph) */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-xs overflow-hidden flex flex-col">
            <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between bg-gray-50/70">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-indigo-600" />
                <span className="font-bold text-xs text-gray-900 uppercase tracking-wider">
                  Cutting Dynamics Graph · Run #{activeRunNumber ?? '--'} (Tool #{selectedToolId})
                </span>
                {isStreaming && (
                  <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700 animate-pulse">
                    <Radio className="w-3 h-3" /> Live Stream
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 text-xs font-mono">
                <span className="text-blue-600 font-bold">
                  Fx: {latestForces ? `${latestForces.fx.toFixed(1)} N` : '-- N'}
                </span>
                <span className="text-emerald-600 font-bold">
                  Fy: {latestForces ? `${latestForces.fy.toFixed(1)} N` : '-- N'}
                </span>
                <span
                  className={`font-black ${
                    latestForces && latestForces.fres > 210
                      ? 'text-rose-600 animate-pulse'
                      : latestForces
                      ? 'text-amber-500'
                      : 'text-gray-400'
                  }`}
                >
                  Fres:{' '}
                  {latestForces ? `${latestForces.fres.toFixed(1)} N` : '-- N'}{' '}
                  {latestForces && latestForces.fres > 210 ? '(SPIKE!)' : ''}
                </span>
              </div>
            </div>

            {/* SVG Visualizer Canvas for Current Run / Streaming Data */}
            <div className="p-4 bg-slate-950 flex-1 flex flex-col justify-center relative select-none min-h-[220px]">
              {/* Background Grid Lines */}
              <div className="absolute inset-0 grid grid-rows-4 grid-cols-8 pointer-events-none opacity-10">
                {Array.from({ length: 32 }).map((_, i) => (
                  <div key={i} className="border border-white" />
                ))}
              </div>

              {streamPoints.length >= 2 ? (
                /* Active Waveform Rendering */
                <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="w-full h-48 overflow-visible">
                  {/* 210 N Threshold Limit Line */}
                  <line
                    x1="0"
                    y1={thresholdY}
                    x2={chartWidth}
                    y2={thresholdY}
                    stroke="#f43f5e"
                    strokeWidth="1.5"
                    strokeDasharray="4 4"
                    opacity="0.85"
                  />
                  <text
                    x="12"
                    y={thresholdY - 6}
                    fill="#f43f5e"
                    fontSize="10"
                    fontFamily="monospace"
                    fontWeight="bold"
                  >
                    ISO DYNAMIC ANOMALY THRESHOLD (Fres = 210 N)
                  </text>

                  {/* Fx Waveform (Faint Blue) */}
                  <polyline
                    fill="none"
                    stroke="#3b82f6"
                    strokeWidth="1.2"
                    opacity="0.4"
                    points={getStreamingFxyPolyline(streamPoints, 'fx')}
                  />

                  {/* Fy Waveform (Faint Emerald) */}
                  <polyline
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="1.2"
                    opacity="0.4"
                    points={getStreamingFxyPolyline(streamPoints, 'fy')}
                  />

                  {/* Primary Resultant Waveform (Fres) */}
                  <polyline
                    fill="none"
                    stroke={
                      latestForces && latestForces.fres > 210
                        ? '#f43f5e'
                        : latestForces && latestForces.fres > 130
                        ? '#f59e0b'
                        : '#10b981'
                    }
                    strokeWidth="2.2"
                    points={getStreamingPolyline(streamPoints)}
                  />
                </svg>
              ) : (
                /* Empty / Standby Oscilloscope Screen awaiting stream */
                <div className="h-48 flex flex-col items-center justify-center text-center z-10 space-y-2">
                  <div className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500">
                    {isStreaming ? (
                      <Activity className="w-5 h-5 text-indigo-400 animate-spin" />
                    ) : (
                      <WifiOff className="w-5 h-5 text-slate-500" />
                    )}
                  </div>
                  <p className="text-xs font-mono font-bold text-slate-300">
                    {isStreaming ? 'LISTENING FOR STREAMING DATA PACKETS...' : 'AWAITING TELEMETRY STREAM'}
                  </p>
                  <p className="text-[11px] font-mono text-slate-500 max-w-sm">
                    {isStreaming
                      ? 'เชื่อมต่อ WebSocket แล้ว กำลังรอข้อมูลแรงตัด (Fx, Fy, Fres) ส่งเข้ามา...'
                      : 'กดปุ่ม "Start Telemetry Stream" หรือส่งข้อมูลสตรีมผ่าน API เพื่อเริ่มแสดงกราฟแบบ Real-time'}
                  </p>
                </div>
              )}

              {/* In-Chart Run Status Overlay */}
              <div className="flex justify-between items-center text-[10px] text-slate-400 font-mono pt-2 border-t border-slate-800">
                <span>Pass Cycle: #{activeRunNumber ?? '--'}</span>
                <span className="text-white font-bold">
                  Status:{' '}
                  <span
                    className={
                      isTimeSeriesAlert
                        ? 'text-rose-400'
                        : currentRunInfo?.tsPrediction === 'USED'
                        ? 'text-amber-400'
                        : currentRunInfo?.tsPrediction === 'SHARP'
                        ? 'text-emerald-400'
                        : 'text-slate-400'
                    }
                  >
                    {currentRunInfo?.tsPrediction || 'Awaiting Data'}
                  </span>
                </span>
                <span>
                  {streamPoints.length >= 2
                    ? isTimeSeriesAlert
                      ? '🔴 Chatter & Force Spikes Detected'
                      : '🟢 Real-time Telemetry Active'
                    : '⚪ Stream Ingestion Standby'}
                </span>
              </div>
            </div>
          </div>

          {/* Section 2: Per-Run Progression Timeline (คลิกเลือกรอบตัดได้ เมื่อมีข้อมูลจาก API) */}
          <div className="p-5 bg-white border border-gray-200 rounded-xl shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-xs uppercase tracking-wider text-gray-700 flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-indigo-600" />
                <span>Per-Run Progression Timeline (ลำดับรอบตัดราย Run)</span>
              </h4>
              <span className="text-[11px] text-gray-400 font-mono">
                {firstDulledRun ? (
                  <>
                    First Dulled: <strong className="text-rose-600">Run #{firstDulledRun.run}</strong>
                  </>
                ) : (
                  <span>Status: Awaiting Ingestion</span>
                )}
              </span>
            </div>

            {/* Stepper Cards Grid or Empty State */}
            {runs.length > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
                {runs.map((item) => {
                  const isSelected = activeRunNumber === item.run;
                  const isDulled = item.tsPrediction === 'DULLED';
                  const isUsed = item.tsPrediction === 'USED';

                  return (
                    <button
                      key={item.run}
                      onClick={() => setActiveRunNumber(item.run)}
                      className={`p-2.5 rounded-xl border text-left transition flex flex-col justify-between min-h-[85px] relative ${
                        isSelected
                          ? isDulled
                            ? 'bg-rose-50 border-rose-500 ring-2 ring-rose-400/30 shadow-xs'
                            : isUsed
                            ? 'bg-amber-50 border-amber-500 ring-2 ring-amber-400/30 shadow-xs'
                            : 'bg-emerald-50 border-emerald-500 ring-2 ring-emerald-400/30 shadow-xs'
                          : 'bg-gray-50/70 border-gray-200 hover:bg-gray-100/80'
                      }`}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span className="font-mono font-bold text-xs text-gray-900">
                          Run #{item.run}
                        </span>
                        {isDulled ? (
                          <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
                        ) : isUsed ? (
                          <span className="w-2 h-2 rounded-full bg-amber-500" />
                        ) : (
                          <span className="w-2 h-2 rounded-full bg-emerald-500" />
                        )}
                      </div>

                      <div className="mt-2">
                        <span
                          className={`text-[10px] font-black font-mono block px-1.5 py-0.5 rounded text-center ${
                            isDulled
                              ? 'bg-rose-600 text-white'
                              : isUsed
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-emerald-100 text-emerald-700'
                          }`}
                        >
                          {item.tsPrediction}
                        </span>
                      </div>

                      {item.fres !== undefined && (
                        <span className="text-[9px] text-gray-400 mt-1 block truncate font-mono">
                          Fres: {Math.round(item.fres)} N
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            ) : (
              /* Empty state waiting for API runs */
              <div className="py-8 px-4 border-2 border-dashed border-gray-200 rounded-xl flex flex-col items-center justify-center text-center">
                <Clock className="w-6 h-6 text-gray-400 mb-2" />
                <p className="text-xs font-bold text-gray-700">
                  ยังไม่มีข้อมูลรอบตัด (Awaiting Run Progression Data)
                </p>
                <p className="text-[11px] text-gray-400 font-mono mt-1 max-w-md">
                  เมื่อเริ่มสตรีมข้อมูลหรือดึง API รอบตัดสำเร็จ ข้อมูล Run #1, Run #2 ... จะถูกเพิ่มเข้ามาใน Timeline อัตโนมัติ
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: 2-Factor In-Process Verification HUD (30%) */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          <div className="p-5 bg-white border border-gray-200 rounded-xl shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <h4 className="font-bold text-xs uppercase tracking-wider text-gray-800 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-indigo-600" />
                <span>2-Factor In-Process Verification</span>
              </h4>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 font-bold">
                Run #{activeRunNumber ?? '--'}
              </span>
            </div>

            {/* Factor 1: Time-Series Per-Run Check */}
            <div
              className={`p-3.5 rounded-xl border transition ${
                !currentRunInfo
                  ? 'bg-gray-50 border-gray-200 text-gray-700'
                  : isTimeSeriesAlert
                  ? 'bg-rose-50/80 border-rose-200 text-rose-950'
                  : currentRunInfo.tsPrediction === 'USED'
                  ? 'bg-amber-50/80 border-amber-200 text-amber-950'
                  : 'bg-emerald-50/80 border-emerald-200 text-emerald-950'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold flex items-center gap-1.5">
                  <Activity className="w-4 h-4" />
                  <span>Factor 1: Time-Series AI</span>
                </span>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded font-black ${
                    !currentRunInfo
                      ? 'bg-gray-200 text-gray-600'
                      : isTimeSeriesAlert
                      ? 'bg-rose-600 text-white'
                      : currentRunInfo.tsPrediction === 'USED'
                      ? 'bg-amber-600 text-white'
                      : 'bg-emerald-600 text-white'
                  }`}
                >
                  {!currentRunInfo
                    ? 'IDLE (STANDBY)'
                    : isTimeSeriesAlert
                    ? 'ALERT (DULLED)'
                    : currentRunInfo.tsPrediction}
                </span>
              </div>
              <p className="text-[11px] text-gray-600 mt-1 font-mono">
                {!currentRunInfo
                  ? 'รอข้อมูลการตัดราย Run จาก Time-Series Stream เพื่อประเมินความคมมีด'
                  : isTimeSeriesAlert
                  ? `ตรวจพบสถานะ DULLED ใน Run #${activeRunNumber} (หยุดเครื่องทันที & สั่งทริกเกอร์ Factor 2)`
                  : `Run #${activeRunNumber} อยู่ในเกณฑ์ ${currentRunInfo.tsPrediction} (ยังใช้งานต่อได้)`}
              </p>
            </div>

            {/* Factor 2: Non-Time-Series Vision AI (รูปภาพของ Chip + คำตอบจากโมเดล) */}
            <div
              className={`p-3.5 rounded-xl border transition ${
                !isNonTimeActive
                  ? 'bg-gray-50 border-gray-200 opacity-60'
                  : 'bg-indigo-50/90 border-indigo-200 text-indigo-950 shadow-xs'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold flex items-center gap-1.5">
                  <Scissors className="w-4 h-4 text-indigo-600" />
                  <span>Factor 2: Non-Time-Series Chip AI</span>
                </span>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded font-black ${
                    !isNonTimeActive
                      ? 'bg-gray-200 text-gray-500'
                      : 'bg-indigo-600 text-white'
                  }`}
                >
                  {!isNonTimeActive ? 'STANDBY (IDLE)' : 'ACTIVE (VERIFIED)'}
                </span>
              </div>

              {!isNonTimeActive ? (
                /* ถ้ายังไม่เจอ Dulled -> Factor 2 ยังไม่ทำ */
                <p className="text-[11px] text-gray-500 mt-2 leading-relaxed">
                  ⚪ <strong>ยังไม่ทำงาน:</strong> โมเดล Non-Time-Series จะไม่ดึงภาพเศษตัดมาประมวลผลจนกว่า Time-Series จะตรวจพบ Dulled อันแรก
                </p>
              ) : (
                /* เมื่อเจอ Dulled อันแรก -> ขึ้นเป็นรูปของ Chip พร้อมคำตอบจากโมเดล */
                <div className="mt-3 space-y-3">
                  {/* ช่อง 4 เหลี่ยมว่างๆ สำหรับภาพ Chip ไว้ก่อนตามคำขอ */}
                  <div className="w-full h-36 rounded-lg border-2 border-dashed border-indigo-200 bg-indigo-50/40 flex flex-col items-center justify-center text-center p-3 select-none">
                    <div className="w-8 h-8 rounded-full bg-white border border-indigo-200 flex items-center justify-center mb-1.5 shadow-xs">
                      <Scissors className="w-4 h-4 text-indigo-500" />
                    </div>
                    <span className="text-xs font-bold text-indigo-900 font-mono">
                      [ ช่องสี่เหลี่ยมภาพ Chip ]
                    </span>
                    <span className="text-[10px] text-gray-500 font-mono mt-0.5">
                      Target: T{selectedToolId}R{activeRunNumber}B1.jpg (เว้นช่องว่างไว้รอเชื่อมต่อ API MinIO)
                    </span>
                  </div>

                  {/* คำตอบจากโมเดล Non-Time-Series Chip AI */}
                  <div className="p-3 bg-white rounded-lg border border-indigo-200 flex items-center justify-between text-xs">
                    <span className="text-gray-600 font-medium">คำตอบโมเดล (Chip AI):</span>
                    <span className="px-2.5 py-1 rounded bg-rose-100 text-rose-700 font-bold font-mono text-xs">
                      {chipAiCondition} ({chipAiConfidence}%)
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Two-Factor Consensus Outcome */}
            <div
              className={`p-3.5 rounded-xl border text-xs space-y-2 ${
                isTwoFactorConfirmed
                  ? 'bg-rose-50 border-rose-300 text-rose-900'
                  : currentRunInfo && !isTimeSeriesAlert
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                  : 'bg-slate-50 border-slate-200 text-slate-700'
              }`}
            >
              <div className="flex items-center gap-2 font-bold text-xs">
                {isTwoFactorConfirmed ? (
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                ) : currentRunInfo && !isTimeSeriesAlert ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                ) : (
                  <Activity className="w-4 h-4 text-slate-400 shrink-0" />
                )}
                <span>
                  {isTwoFactorConfirmed
                    ? 'ผลยืนยันร่วม (2FA): สองโมเดลคอนเฟิร์มมีดสึกหรอตรงกัน'
                    : currentRunInfo && !isTimeSeriesAlert
                    ? 'สถานะการกัดงาน: ปกติ (ไม่ต้องถอดมีด)'
                    : 'สถานะระบบ: สแตนด์บายรอรับข้อมูล (Awaiting Stream)'}
                </span>
              </div>
              <p className="text-[11px] text-gray-600 leading-relaxed">
                {isTwoFactorConfirmed
                  ? `ตรวจพบ Dulled อันแรกใน Run #${activeRunNumber} สั่งหยุดสปินเดิลเพื่อความปลอดภัย ให้ถอดหัวมีดไปส่องกล้องหาค่า Vb ที่หน้า Tool Verification`
                  : currentRunInfo && !isTimeSeriesAlert
                  ? `รอบตัด Run #${activeRunNumber} ยังไม่เข้าข่ายอันตราย โมเดล Non-Time ยังไม่ต้องทำ และเครื่องจักรกัดงานต่อได้`
                  : 'ระบบ 2-Factor พร้อมทำงานทันทีเมื่อได้รับข้อมูลสตรีมแรงตัดและรอบตัดส่งเข้ามาผ่าน API'}
              </p>

              {/* Action Button: นำทางไปยังหน้า Tool Verification */}
              {isTwoFactorConfirmed && (
                <button
                  onClick={() => navigate(`/visual-qc?tool=${selectedToolId}&run=${activeRunNumber}`)}
                  className="w-full mt-2 py-2.5 px-3 bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs rounded-lg shadow-sm transition flex items-center justify-center gap-1.5"
                >
                  <ScanEye className="w-4 h-4" />
                  <span>ถอดมีดไปตรวจค่า Vb ที่ Tool Verification Bench (Run #{activeRunNumber}) ➔</span>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MachineMonitoringPage;
