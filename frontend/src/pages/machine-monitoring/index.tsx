import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
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
  Wrench,
} from 'lucide-react';
import { PageHeader } from '../../components/common/PageHeader';
import { StatusBadge } from '../../components/common/StatusBadge';
import { api } from '../../services/api';

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
  const [searchParams] = useSearchParams();

  // Active Tool state (read from URL params if navigated from Dashboard)
  const [selectedToolId, setSelectedToolId] = useState<number>(() => {
    const toolParam = searchParams.get('tool');
    return toolParam ? Number(toolParam) : 10;
  });

  // Per-Run Progression items (Clean / empty by default awaiting API or stream)
  const [runs, setRuns] = useState<RunProgressionItem[]>([]);
  const [activeRunNumber, setActiveRunNumber] = useState<number | null>(null);

  // Active in-progress pass metadata during live cutting
  const [activeCuttingRun, setActiveCuttingRun] = useState<number>(1);
  const [activeCuttingProgressPct, setActiveCuttingProgressPct] = useState<number>(0);

  // Live streaming buffer (rolling window of the latest data points)
  const [streamPoints, setStreamPoints] = useState<StreamingDataPoint[]>([]);
  const [latestForces, setLatestForces] = useState<{
    fx: number;
    fy: number;
    fz?: number;
    fres: number;
  } | null>(null);

  // Stream connection state (restores streaming flag from sessionStorage if user previously turned it on)
  const [isStreaming, setIsStreaming] = useState<boolean>(() => {
    try {
      return sessionStorage.getItem('pdm_streaming_active') === 'true';
    } catch {
      return false;
    }
  });
  const [streamStatus, setStreamStatus] = useState<'IDLE' | 'CONNECTING' | 'STREAMING' | 'ERROR'>('IDLE');
  const wsRef = useRef<WebSocket | null>(null);

  const [machineStatus, setMachineStatus] = useState<{
    status: string;
    isStopped: boolean;
    currentRun: number;
    stoppedRun?: number;
    stopReason?: string;
  } | null>(null);

  // Sync machine hardware status and milling history periodically
  useEffect(() => {
    let isMounted = true;

    const syncMachineAndHistory = () => {
      api.getMachineStatus().then((ms) => {
        if (isMounted && ms) {
          setMachineStatus(ms);
          if (ms.status === 'RUNNING') {
            setIsStreaming(true);
            try { sessionStorage.setItem('pdm_streaming_active', 'true'); } catch {}
          } else if (ms.isStopped) {
            setIsStreaming(false);
            try { sessionStorage.removeItem('pdm_streaming_active'); } catch {}
          }
        }
      });

      api.getMillingHistory()
        .then((data: any) => {
          if (!isMounted || !data) return;
          if (Array.isArray(data.runs) && data.runs.length > 0) {
            const loadedRuns: RunProgressionItem[] = data.runs.map((r: any) => ({
              run: r.run,
              tsPrediction: r.tsPrediction,
              confidence: r.confidence ?? 0.95,
              flankWearUm: r.flankWearUm,
              gapsUm: r.chippingGapUm,
              fres: r.fres,
            }));
            setRuns(loadedRuns);
            setActiveRunNumber((prev) => prev ?? loadedRuns[loadedRuns.length - 1].run);
            try {
              sessionStorage.setItem('milling_runs_cache', JSON.stringify(loadedRuns));
            } catch {}
          } else if (data.currentRun) {
            setActiveCuttingRun(data.currentRun);
          }
        })
        .catch((err: any) => {
          console.warn('[Telemetry] History fetch error:', err);
        });
    };

    // Fast local restore from sessionStorage to eliminate UI flash
    try {
      const cached = sessionStorage.getItem('milling_runs_cache');
      if (cached) {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setRuns(parsed);
          setActiveRunNumber(parsed[parsed.length - 1].run);
        }
      }
    } catch {}

    syncMachineAndHistory();
    const interval = setInterval(syncMachineAndHistory, 2500);
    window.addEventListener('focus', syncMachineAndHistory);

    return () => {
      isMounted = false;
      clearInterval(interval);
      window.removeEventListener('focus', syncMachineAndHistory);
    };
  }, []);

  // Automatically load and display waveform curve for the active run when returning to the page or selecting a run
  useEffect(() => {
    if (isStreaming) return;
    const targetRun = activeRunNumber ?? (runs.length > 0 ? runs[runs.length - 1].run : null);
    if (!targetRun) return;

    let isMounted = true;
    api.getRunWaveform(selectedToolId, targetRun).then((points: StreamingDataPoint[]) => {
      if (!isMounted || !Array.isArray(points) || points.length === 0) return;
      setStreamPoints(points);
      const last = points[points.length - 1];
      setLatestForces({
        fx: last.fx,
        fy: last.fy,
        fz: last.fz,
        fres: last.fres,
      });
    });

    return () => {
      isMounted = false;
    };
  }, [activeRunNumber, isStreaming, selectedToolId, runs.length]);

  // Active run info derived from current runs array
  const currentRunInfo = runs.find((r) => r.run === activeRunNumber) || (runs.length > 0 ? runs[runs.length - 1] : null);
  const isTimeSeriesAlert = currentRunInfo?.tsPrediction === 'DULLED';

  // Two-Factor Logic:
  // Factor 1: Time-Series Force AI checks per-run.
  // Factor 2: Non-Time-Series Chip AI triggers ONLY IF Factor 1 Alerts!
  const isNonTimeActive = Boolean(currentRunInfo && isTimeSeriesAlert);
  const chipAiCondition = currentRunInfo?.chipPrediction || (isTimeSeriesAlert ? 'PENDING' : 'SHARP');
  const chipAiConfidence = currentRunInfo?.chipConfidence ?? 0;
  const isTwoFactorConfirmed = Boolean(isTimeSeriesAlert && chipAiCondition === 'DULLED');

  useEffect(() => {
    let isMounted = true;
    if (isTimeSeriesAlert && activeRunNumber && !currentRunInfo?.chipPrediction) {
      api.getBladeQc(selectedToolId, activeRunNumber, 1).then((res: any) => {
        if (!isMounted) return;
        if (res && res.tier2ChipAi) {
          setRuns((prev) => prev.map((r) => r.run === activeRunNumber ? {
            ...r,
            chipPrediction: res.tier2ChipAi.condition,
            chipConfidence: res.tier2ChipAi.confidence
          } : r));
        }
      }).catch(console.error);
    }
    return () => { isMounted = false; };
  }, [isTimeSeriesAlert, activeRunNumber, currentRunInfo?.chipPrediction, selectedToolId]);

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

          // Update live milling progress for current cutting pass
          if (data.passIndex !== undefined) {
            setActiveCuttingRun(Number(data.passIndex));
          }
          if (data.runProgressPct !== undefined) {
            setActiveCuttingProgressPct(Number(data.runProgressPct));
          }

          // Evaluate Time-Series model prediction ONLY when the pass has finished cutting!
          if (data.isPassCompleted && data.inference && data.inference.status === 'COMPLETED') {
            const passNum = Number(data.passIndex);
            const condition = data.inference.condition;
            const conf = data.inference.confidence || 0.95;
            const flankWear = data.inference.flankWearUm;

            setRuns((prev) => {
              const idx = prev.findIndex((r) => r.run === passNum);
              const item: RunProgressionItem = {
                run: passNum,
                tsPrediction: condition,
                confidence: conf,
                flankWearUm: flankWear,
                fres: data.forces.fres,
              };
              let next;
              if (idx >= 0) {
                next = [...prev];
                next[idx] = item;
              } else {
                next = [...prev, item].sort((a, b) => a.run - b.run);
              }
              try {
                sessionStorage.setItem('milling_runs_cache', JSON.stringify(next));
              } catch {}
              return next;
            });

            // Follow active milling run dynamically
            setActiveRunNumber(passNum);

            // Safety Interlock: If Time-Series model detects DULLED, auto-stop stream
            if (condition === 'DULLED' || data.machineState === 'EMERGENCY_HALTED') {
              setIsStreaming(false); // Safety cut on first dulled!
              try {
                sessionStorage.removeItem('pdm_streaming_active');
              } catch {}
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
        socket.onclose = null;
        socket.onerror = null;
        socket.onmessage = null;
        socket.close();
      }
      wsRef.current = null;
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

  const handleToggleStreaming = async () => {
    if (!isStreaming) {
      if (
        machineStatus?.isStopped &&
        machineStatus?.stopReason?.includes('Safety Interlock') &&
        !machineStatus?.stopReason?.includes('QC_CLEARED')
      ) {
        alert(
          '⚠️ ไม่สามารถเริ่มทำงานได้เนื่องจาก Safety Interlock ถูกทริป (หัวมีดสึกหรอระดับ DULL)\nกรุณากดปุ่ม "Mount Fresh Tool (Reset)" เพื่อเปลี่ยนหัวมีดก่อน'
        );
        return;
      }
      try {
        const res = await api.startMachine();
        if (res && res.success === false) {
          alert(`⚠️ ไม่สามารถเริ่มเครื่องจักรได้: ${res.detail || 'เกิดข้อผิดพลาด'}`);
          return;
        }
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ command: 'START_STREAM' }));
        }
        setIsStreaming(true);
        sessionStorage.setItem('pdm_streaming_active', 'true');
        const ms = await api.getMachineStatus();
        if (ms) setMachineStatus(ms);
      } catch (err: any) {
        console.error('Failed to start machine:', err);
      }
    } else {
      try {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ command: 'PAUSE_STREAM' }));
        }
        await api.pauseMachine('Operator paused cutting stream');
        setIsStreaming(false);
        sessionStorage.removeItem('pdm_streaming_active');
        const ms = await api.getMachineStatus();
        if (ms) setMachineStatus(ms);
      } catch (err: any) {
        console.error('Failed to pause machine:', err);
      }
    }
  };

  const handleClearData = () => {
    setStreamPoints([]);
    setLatestForces(null);
    setRuns([]);
    setActiveRunNumber(null);
    setActiveCuttingProgressPct(0);
    try {
      sessionStorage.removeItem('milling_runs_cache');
      sessionStorage.removeItem('pdm_streaming_active');
    } catch {}
  };

  const handleMountFreshTool = async () => {
    try {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ command: 'MOUNT_FRESH_TOOL' }));
      }
      await api.resetMachine();
    } catch {
      // ignore
    }
    setStreamPoints([]);
    setLatestForces(null);
    setRuns([]);
    setActiveRunNumber(1);
    setActiveCuttingRun(1);
    setActiveCuttingProgressPct(0);
    try {
      sessionStorage.removeItem('milling_runs_cache');
      sessionStorage.removeItem('pdm_streaming_active');
    } catch {}
    setIsStreaming(false);
    const ms = await api.getMachineStatus();
    if (ms) setMachineStatus(ms);
  };

  const handleResumeSpindle = async () => {
    try {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ command: 'RESUME' }));
      }
      const targetMachineId = (machineStatus as any)?.machineId || 'CNC-SP-01';
      await api.controlSpindle('RESUME', targetMachineId);
      const ms = await api.getMachineStatus();
      if (ms) setMachineStatus(ms);
      setIsStreaming(true);
      try { sessionStorage.setItem('pdm_streaming_active', 'true'); } catch {}
    } catch (err: any) {
      console.error('Failed to resume spindle:', err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <PageHeader
        title="Time-Series Per-Run Progression & 2-Factor In-Process Tracking"
        subtitle="โมเดล Time-Series CRNN (BiGRU + Attention) เช็คราย Run ตามลำดับรอบตัด ➔ หยุดทันทีเมื่อเจอ Dulled อันแรก เพื่อดึงภาพ Chip"
        actions={
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-gray-50 text-xs font-mono font-bold text-gray-800 shadow-2xs">
              <Wrench className="w-3.5 h-3.5 text-indigo-600" />
              <span>Tool #{selectedToolId}</span>
            </div>
            {/* Mount Fresh Tool / Reset Spindle Button */}
            <button
              onClick={handleMountFreshTool}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border border-emerald-300 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 transition shadow-xs cursor-pointer"
              title="เปลี่ยนหัวมีดใหม่ (Mount Fresh Tool) และรีเซ็ตการตัดเริ่มจาก Run #1"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Mount Fresh Tool (Reset)</span>
            </button>

            {/* Clear Buffer Button */}
            {(runs.length > 0 || streamPoints.length > 0) && (
              <button
                onClick={handleClearData}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border border-gray-200 bg-white hover:bg-gray-50 text-gray-600 transition shadow-xs cursor-pointer"
                title="ล้างข้อมูลกราฟและรอบตัดเพื่อเริ่มรับข้อมูลใหม่"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Clear Buffer</span>
              </button>
            )}

            {/* Live Streaming Toggle */}
            <button
              onClick={handleToggleStreaming}
              className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold border transition shadow-xs cursor-pointer ${
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

      {/* Safety Interlock Auto-Halt Alert Banner */}
      {isTimeSeriesAlert && (
        <div className={`p-4 bg-gradient-to-r ${
          machineStatus?.stopReason?.includes('QC_CLEARED')
            ? 'from-emerald-950 via-slate-900 to-emerald-950 border-emerald-800/70'
            : 'from-rose-950 via-slate-900 to-rose-950 border-rose-800/70'
        } text-white rounded-xl shadow-sm border flex flex-wrap items-center justify-between gap-4 animate-in fade-in duration-200`}>
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-lg border ${
              machineStatus?.stopReason?.includes('QC_CLEARED')
                ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
                : 'bg-rose-500/20 border-rose-500/40 text-rose-300'
            }`}>
              <AlertTriangle className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className={`text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border font-bold ${
                  machineStatus?.stopReason?.includes('QC_CLEARED')
                    ? 'bg-emerald-500/30 border-emerald-500/50 text-emerald-200'
                    : machineStatus?.stopReason?.includes('QC_CONFIRMED')
                    ? 'bg-rose-500/30 border-rose-500/50 text-rose-200'
                    : 'bg-amber-500/30 border-amber-500/50 text-amber-200'
                }`}>
                  {machineStatus?.stopReason?.includes('QC_CLEARED')
                    ? '✅ QC Cleared · Tool Verified Safe (False Alarm)'
                    : machineStatus?.stopReason?.includes('QC_CONFIRMED')
                    ? '🛑 QC Confirmed · Wear Verified (DULLED) — Fresh Tool Required'
                    : `🛑 Safety Interlock Triggered · Spindle Halted at Run #${activeRunNumber}`}
                </span>
                <span className="text-xs text-slate-300 font-mono">
                  Tool Condition: {currentRunInfo?.tsPrediction || 'DULLED'} ({((currentRunInfo?.confidence ?? 0.95) * 100).toFixed(1)}% Conf)
                </span>
              </div>
              <p className="text-xs text-slate-200 mt-1">
                {machineStatus?.stopReason?.includes('QC_CLEARED')
                  ? 'วิศวกรผู้เชี่ยวชาญได้ตรวจสอบภาพถ่ายคมมีดที่แท่นส่องกล้องแล้ว ยืนยันว่าคมมีดยังไม่สึกหรอวิกฤต (False Alarm) — ระบบอนุมัติให้เดินเครื่องตัดต่อได้'
                  : machineStatus?.stopReason?.includes('QC_CONFIRMED')
                  ? 'วิศวกรผู้เชี่ยวชาญตรวจสอบคมมีดที่แท่นส่องกล้องแล้ว ยืนยันว่ามีดสึกหรอวิกฤต (DULLED) จริง — กรุณากด "เปลี่ยนมีดใหม่" เพื่อเริ่มรอบตัดใหม่ด้วยมีดชุดใหม่'
                  : `สปินเดิลและระบบสตรีมถูกสั่งหยุดการทำงานอัตโนมัติ เนื่องจากโมเดล Time-Series CRNN ตรวจพบว่ามีดอยู่ในสถานะ DULLED ในรอบตัด Pass #${activeRunNumber} กรุณาถอดมีดไปตรวจยืนยันที่แท่นส่องกล้อง`}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {machineStatus?.stopReason?.includes('QC_CLEARED') ? (
              <button
                onClick={handleResumeSpindle}
                className="px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-sm transition flex items-center gap-1.5 cursor-pointer ring-2 ring-emerald-400/50"
              >
                <Activity className="w-3.5 h-3.5" />
                <span>ปลดล็อคและเดินเครื่องต่อ (Resume Cutting)</span>
              </button>
            ) : (
              <button
                onClick={() => navigate(`/visual-qc?tool=${selectedToolId}&run=${activeRunNumber}`)}
                className={`px-3.5 py-2 rounded-lg font-bold text-xs shadow-sm transition flex items-center gap-1.5 cursor-pointer ${
                  machineStatus?.stopReason?.includes('QC_CONFIRMED')
                    ? 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700'
                    : 'bg-rose-600 hover:bg-rose-500 text-white animate-pulse'
                }`}
              >
                <ScanEye className="w-3.5 h-3.5" />
                <span>{machineStatus?.stopReason?.includes('QC_CONFIRMED') ? 'ดูผลการตรวจที่ Visual QC' : 'ถอดมีดไปตรวจที่ Tool Verification'}</span>
              </button>
            )}
            <button
              onClick={handleMountFreshTool}
              className={`px-3.5 py-2 rounded-lg font-bold text-xs transition flex items-center gap-1.5 cursor-pointer ${
                machineStatus?.stopReason?.includes('QC_CONFIRMED')
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm ring-2 ring-emerald-400/50'
                  : 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700'
              }`}
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>เปลี่ยนมีดใหม่ (Mount Fresh Tool)</span>
            </button>
          </div>
        </div>
      )}

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
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold hidden sm:inline-block" title="Piezoelectric dynamometer sampling rate 1,000 Hz decimated to 20 Hz for web telemetry">
                  Sensor: 1 kHz Raw · Stream: 20 Hz
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

              {/* Live Milling Pass In-Progress Bar */}
              {isStreaming && (
                <div className="bg-slate-900/90 rounded-lg p-2.5 my-2 border border-slate-800 flex items-center justify-between text-xs font-mono">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                    <span className="text-slate-200 font-bold">
                      Workpiece Milling Pass #{activeCuttingRun}:
                    </span>
                    <span className="text-emerald-400 font-bold">
                      {activeCuttingProgressPct.toFixed(0)}%
                    </span>
                  </div>
                  <div className="flex-1 max-w-xs mx-4 bg-slate-800 rounded-full h-2 overflow-hidden border border-slate-700">
                    <div
                      className="bg-emerald-500 h-full transition-all duration-100 ease-out"
                      style={{ width: `${Math.min(100, Math.max(0, activeCuttingProgressPct))}%` }}
                    />
                  </div>
                  <span className="text-slate-400 text-[11px] hidden sm:inline">
                    CRNN Model evaluates at 100%
                  </span>
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
                  {/* Image container for real Chip morphology photo */}
                  <div className="w-full h-40 rounded-lg overflow-hidden border border-indigo-200 bg-slate-900 flex flex-col items-center justify-center relative select-none">
                    <img
                      src={`${(import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api/v1'}/qc/images/chip/T${selectedToolId}R${activeRunNumber}B1.jpg`}
                      alt={`Chip morphology T${selectedToolId}R${activeRunNumber}`}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = 'none';
                      }}
                    />
                    <div className="absolute bottom-1 right-1 px-1.5 py-0.5 rounded bg-black/75 text-[9px] font-mono text-white">
                      T{selectedToolId}R{activeRunNumber}B1.jpg
                    </div>
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
                  ? `ตรวจพบ Dulled อันแรกใน Run #${activeRunNumber} สั่งหยุดสปินเดิลเพื่อความปลอดภัย ให้ถอดหัวมีดไปส่องกล้องตรวจสภาพคมมีดที่หน้า Tool Verification`
                  : currentRunInfo && !isTimeSeriesAlert
                  ? `รอบตัด Run #${activeRunNumber} ยังไม่เข้าข่ายอันตราย โมเดล Non-Time ยังไม่ต้องทำ และเครื่องจักรกัดงานต่อได้`
                  : 'ระบบ 2-Factor พร้อมทำงานทันทีเมื่อได้รับข้อมูลสตรีมแรงตัดและรอบตัดส่งเข้ามาผ่าน API'}
              </p>

              {/* Action Button: นำทางไปยังหน้า Tool Verification */}
              {isTwoFactorConfirmed && (
                <button
                  onClick={() => navigate(`/visual-qc?tool=${selectedToolId}&run=${activeRunNumber}`)}
                  className="w-full mt-2 py-2.5 px-3 bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs rounded-lg shadow-sm transition flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  <ScanEye className="w-4 h-4" />
                  <span>ถอดมีดไปตรวจสภาพคมมีดจริงที่ Tool Verification Bench (Run #{activeRunNumber}) ➔</span>
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
