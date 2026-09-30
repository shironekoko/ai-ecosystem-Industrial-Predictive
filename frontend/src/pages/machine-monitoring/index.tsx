import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  Play,
  Pause,
  RotateCcw,
  Gauge,
  ScanEye,
  Wifi,
  WifiOff,
  ShieldAlert,
  Clock,
} from 'lucide-react';
import { PageHeader } from '../../components/common/PageHeader';
import { StatusBadge } from '../../components/common/StatusBadge';
import { telemetryStream } from '../../services/telemetryStream';
import { TelemetryPacket, StreamConnectionStatus } from '../../types';

export function MachineMonitoringPage() {
  const navigate = useNavigate();

  // Stream state received from TelemetryStreamService
  const [streamStatus, setStreamStatus] = useState<StreamConnectionStatus>('CONNECTING');
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [latestPacket, setLatestPacket] = useState<TelemetryPacket | null>(null);

  // Rolling Oscilloscope Window Buffer (FIFO: 80 points)
  const BUFFER_SIZE = 80;
  const [bufferFx, setBufferFx] = useState<number[]>(() => Array(BUFFER_SIZE).fill(0));
  const [bufferFy, setBufferFy] = useState<number[]>(() => Array(BUFFER_SIZE).fill(0));
  const [bufferFz, setBufferFz] = useState<number[]>(() => Array(BUFFER_SIZE).fill(0));

  // Subscribe to Telemetry Stream & Connection Status
  useEffect(() => {
    const unsubStatus = telemetryStream.subscribeStatus((status) => {
      setStreamStatus(status);
    });

    const unsubPacket = telemetryStream.subscribe((packet) => {
      setLatestPacket(packet);

      // Append waveform chunk to rolling FIFO buffer
      const chunk = packet.waveformChunk;
      if (chunk && chunk.fx.length > 0) {
        setBufferFx((prev) => [...prev.slice(chunk.fx.length), ...chunk.fx]);
        setBufferFy((prev) => [...prev.slice(chunk.fy.length), ...chunk.fy]);
        setBufferFz((prev) => [...prev.slice(chunk.fz.length), ...chunk.fz]);
      } else {
        setBufferFx((prev) => [...prev.slice(1), packet.forces.fx]);
        setBufferFy((prev) => [...prev.slice(1), packet.forces.fy]);
        setBufferFz((prev) => [...prev.slice(1), packet.forces.fz]);
      }
    });

    return () => {
      unsubStatus();
      unsubPacket();
    };
  }, []);

  // Control handlers
  const handleTogglePlay = () => {
    if (isPaused) {
      telemetryStream.resume();
      setIsPaused(false);
    } else {
      telemetryStream.pause();
      setIsPaused(true);
    }
  };

  const handleReconnect = () => {
    telemetryStream.reconnect();
    setBufferFx(Array(BUFFER_SIZE).fill(0));
    setBufferFy(Array(BUFFER_SIZE).fill(0));
    setBufferFz(Array(BUFFER_SIZE).fill(0));
    setLatestPacket(null);
  };

  // Derive display values from incoming packet or keep clean standby state
  const isConnected = streamStatus === 'CONNECTED' && latestPacket !== null;
  const passIndex = latestPacket?.passIndex ?? null;
  const cycleDurationSec = latestPacket?.cycleDurationSec ?? 0;
  const machineState = latestPacket?.machineState ?? 'STANDBY';
  const isInterlockTripped = latestPacket?.interlockStatus === 'TRIPPED';
  const interlockReason = latestPacket?.interlockReason;
  const inference = latestPacket?.inference ?? null;
  const forces = latestPacket?.forces ?? { fx: 0, fy: 0, fz: 0, fres: 0 };

  // Calculate real CNC mechanical telemetry metrics
  const spindleLoadPct = isConnected ? Math.min(100, Math.round((forces.fres / 260) * 100)) : 0;
  const stabilityStatus = !isConnected
    ? { label: 'STREAM STANDBY', color: 'text-gray-500 bg-gray-50 border-gray-200' }
    : forces.fres > 210
    ? { label: 'CRITICAL CHATTER / IMPACT', color: 'text-rose-600 bg-rose-50 border-rose-200' }
    : forces.fres > 140
    ? { label: 'ELEVATED FRICTION LOAD', color: 'text-amber-600 bg-amber-50 border-amber-200' }
    : { label: 'STABLE CUTTING DYNAMICS', color: 'text-emerald-600 bg-emerald-50 border-emerald-200' };

  // SVG Chart Dimensions
  const chartHeight = 220;
  const chartWidth = 720;

  const makePolyline = (arr: number[]) => {
    const minVal = -50;
    const maxVal = 320;
    return arr
      .map((val, i) => {
        const x = (i / (BUFFER_SIZE - 1)) * chartWidth;
        const normalized = Math.max(0, Math.min(1, (val - minVal) / (maxVal - minVal)));
        const y = chartHeight - normalized * chartHeight;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <PageHeader
        title="Live Spindle Force Telemetry & Prognostics"
        subtitle="Real-time High-Frequency Cutting Dynamics · Dynamometer In-Process Tracking (Pure Time-Series CRNN: TCN + BiGRU)"
        actions={
          <div className="flex items-center gap-2">
            <span
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md font-semibold border ${
                streamStatus === 'CONNECTED'
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-amber-50 text-amber-700 border-amber-200'
              }`}
              title={telemetryStream.getWsUrl()}
            >
              {streamStatus === 'CONNECTED' ? (
                <Wifi className="w-3.5 h-3.5 text-emerald-600" />
              ) : (
                <WifiOff className="w-3.5 h-3.5 text-amber-600" />
              )}
              <span>
                {streamStatus === 'CONNECTED'
                  ? 'WebSocket: Live Feed'
                  : 'Stream Standby (Awaiting API)'}
              </span>
            </span>

            <StatusBadge
              status={isInterlockTripped ? 'critical' : isPaused ? 'warning' : isConnected ? 'connected' : 'disconnected'}
              label={
                isInterlockTripped
                  ? 'SAFETY E-STOP'
                  : isPaused
                  ? 'STREAM PAUSED'
                  : isConnected
                  ? 'LIVE TELEMETRY'
                  : 'STREAM STANDBY'
              }
            />
          </div>
        }
      />

      {/* Emergency Machine Halt Interlock Banner (Shown only when real safety trip occurs) */}
      {isInterlockTripped && (
        <div className="p-4 rounded-xl bg-rose-600 text-white shadow-xl border border-rose-500 flex flex-wrap items-center justify-between gap-4 animate-fadeIn">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-white/20 rounded-xl text-white">
              <ShieldAlert className="w-7 h-7 animate-bounce" />
            </div>
            <div>
              <p className="font-black text-sm uppercase tracking-wider flex items-center gap-2">
                <span>🔴 EMERGENCY INTERLOCK TRIPPED · SPINDLE FEED CUT</span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-white text-rose-700 font-mono font-bold">
                  SAFETY RELAY OPEN
                </span>
              </p>
              <p className="text-xs text-rose-100 mt-1 max-w-2xl leading-relaxed">
                {interlockReason ||
                  'Spindle cutting load and friction exceeded critical tolerance limits. Motor feed halted automatically to prevent workpiece gouging. Send tool to Optical Verification.'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate(passIndex ? `/visual-qc?run=${passIndex}` : `/visual-qc`)}
              className="flex items-center gap-1.5 px-4 py-2 bg-white text-rose-700 hover:bg-rose-50 text-xs font-bold rounded-lg shadow-md transition"
            >
              <ScanEye className="w-4 h-4" />
              <span>Inspect Blades in Tool Verification</span>
            </button>
            <button
              onClick={handleReconnect}
              className="px-3.5 py-2 bg-rose-800 hover:bg-rose-900 text-white text-xs font-semibold rounded-lg border border-rose-400/50 transition flex items-center gap-1"
              title="Reset connection"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reconnect Stream</span>
            </button>
          </div>
        </div>
      )}

      {/* Stream Control & Spindle Telemetry Ribbon */}
      <div className="p-4 bg-white border border-gray-200 rounded-xl shadow-sm flex flex-wrap items-center justify-between gap-4">
        {/* Left: Stream Control & Spindle Status */}
        <div className="flex items-center gap-3">
          <button
            disabled={!isConnected}
            onClick={handleTogglePlay}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border transition ${
              !isConnected
                ? 'opacity-40 cursor-not-allowed bg-gray-100 text-gray-400 border-gray-200'
                : isPaused
                ? 'bg-emerald-50 text-emerald-700 border-emerald-300 hover:bg-emerald-100'
                : 'bg-amber-50 text-amber-700 border-amber-300 hover:bg-amber-100'
            }`}
          >
            {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
            <span>{isPaused ? 'Resume Live Stream' : 'Pause Live Feed'}</span>
          </button>

          <button
            onClick={handleReconnect}
            className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-100 transition"
            title="Reconnect WebSocket stream"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          {/* Machining Cycle Indicator */}
          <div className="px-3 py-1.5 rounded-lg bg-gray-100 border border-gray-200 text-gray-800 text-xs font-mono font-bold flex items-center gap-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                isInterlockTripped
                  ? 'bg-rose-600 animate-ping'
                  : isConnected && machineState === 'ENGAGED'
                  ? 'bg-emerald-500 animate-pulse'
                  : 'bg-gray-400'
              }`}
            />
            <span>
              Machining Pass:{' '}
              <strong className="text-indigo-600 font-black">
                {passIndex !== null ? `#${passIndex}` : '--'}
              </strong>{' '}
              · Phase:{' '}
              <strong
                className={
                  isInterlockTripped
                    ? 'text-rose-600'
                    : isConnected && machineState === 'ENGAGED'
                    ? 'text-emerald-700'
                    : 'text-gray-500'
                }
              >
                {isInterlockTripped ? 'EMERGENCY HALTED' : machineState}
              </strong>
            </span>
          </div>

          <div className="flex items-center gap-1.5 text-xs text-gray-500 font-mono">
            <Clock className="w-3.5 h-3.5 text-gray-400" />
            <span>Pass Elapsed: {cycleDurationSec}s</span>
          </div>
        </div>

        {/* Right: Optical QC Shortcut */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate(passIndex ? `/visual-qc?run=${passIndex}` : `/visual-qc`)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold shadow-sm transition"
          >
            <ScanEye className="w-3.5 h-3.5" />
            <span>
              {passIndex !== null
                ? `Open Tool Verification Station (Pass #${passIndex})`
                : 'Open Tool Verification Station'}
            </span>
          </button>
        </div>
      </div>

      {/* Main Monitoring Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left: Continuous Oscilloscope Waveform Display */}
        <div className="col-span-12 lg:col-span-8 bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
          <div className="px-6 py-3.5 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
            <div>
              <h3 className="font-bold text-gray-900 text-sm flex items-center gap-2">
                <Activity className="w-4 h-4 text-rose-600" />
                <span>Continuous Oscilloscope (Tri-Axial Dynamometer)</span>
              </h3>
              <p className="text-xs text-gray-500 mt-0.5 font-mono">
                Streaming 4-Flute Tooth Passing Dynamics · 1 kHz Native Sampling
              </p>
            </div>
            {/* Chart Legend */}
            <div className="flex items-center gap-3 text-xs font-mono font-semibold">
              <span className="flex items-center gap-1.5 text-sky-400">
                <span className="w-2.5 h-2.5 rounded-full bg-sky-400" /> Fx (Feed)
              </span>
              <span className="flex items-center gap-1.5 text-emerald-400">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" /> Fy (Normal)
              </span>
              <span className="flex items-center gap-1.5 text-purple-400">
                <span className="w-2.5 h-2.5 rounded-full bg-purple-400" /> Fz (Axial)
              </span>
            </div>
          </div>

          {/* SVG Waveform Rendering */}
          <div className="p-6 flex-1 flex flex-col justify-center bg-slate-950 rounded-b-xl relative overflow-hidden">
            {/* Oscilloscope Grid */}
            <div className="absolute inset-0 grid grid-cols-8 grid-rows-4 pointer-events-none opacity-10">
              {Array.from({ length: 32 }).map((_, i) => (
                <div key={i} className="border border-white" />
              ))}
            </div>

            {/* Standby Banner when disconnected */}
            {!isConnected && (
              <div className="absolute inset-0 flex items-center justify-center bg-slate-950/80 z-10 pointer-events-none select-none">
                <div className="text-center space-y-1">
                  <Activity className="w-8 h-8 text-slate-600 mx-auto stroke-[1.2]" />
                  <p className="text-xs font-mono font-bold text-slate-400 uppercase tracking-widest">
                    Awaiting Telemetry Stream
                  </p>
                  <p className="text-[11px] font-mono text-slate-600">
                    ws://localhost:8000/api/v1/telemetry/spindle/stream
                  </p>
                </div>
              </div>
            )}

            <svg
              viewBox={`0 0 ${chartWidth} ${chartHeight}`}
              className="w-full h-56 select-none overflow-visible"
            >
              {/* Zero Reference Line */}
              <line
                x1="0"
                y1={chartHeight * 0.85}
                x2={chartWidth}
                y2={chartHeight * 0.85}
                stroke="#334155"
                strokeWidth="1"
                strokeDasharray="4 4"
              />

              {/* Fx Waveform (Sky Blue) */}
              <polyline
                fill="none"
                stroke="#38bdf8"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={makePolyline(bufferFx)}
              />

              {/* Fy Waveform (Emerald) */}
              <polyline
                fill="none"
                stroke="#34d399"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={makePolyline(bufferFy)}
              />

              {/* Fz Waveform (Purple - Dominant Axial Force) */}
              <polyline
                fill="none"
                stroke="#c084fc"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={makePolyline(bufferFz)}
              />
            </svg>

            {/* Live Instantaneous Force Meters */}
            <div className="mt-4 pt-3 border-t border-slate-800 grid grid-cols-4 gap-2 text-center font-mono">
              <div className="bg-slate-900/90 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block uppercase">Fx (Feed)</span>
                <span className="text-sm font-bold text-sky-400">
                  {isConnected ? `${forces.fx} N` : '-- N'}
                </span>
              </div>
              <div className="bg-slate-900/90 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block uppercase">Fy (Normal)</span>
                <span className="text-sm font-bold text-emerald-400">
                  {isConnected ? `${forces.fy} N` : '-- N'}
                </span>
              </div>
              <div className="bg-slate-900/90 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block uppercase">Fz (Axial)</span>
                <span className="text-sm font-bold text-purple-400">
                  {isConnected ? `${forces.fz} N` : '-- N'}
                </span>
              </div>
              <div className="bg-slate-900/90 p-2 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block uppercase">Fres (Resultant)</span>
                <span className="text-sm font-bold text-amber-400">
                  {isConnected ? `${forces.fres} N` : '-- N'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right: In-Process Spindle Telemetry & Cutting Diagnostics HUD */}
        <div className="col-span-12 lg:col-span-4 space-y-5">
          {/* Main Cutting Stability & Force State */}
          <div className="p-6 bg-white border border-gray-200 rounded-xl shadow-sm text-center">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block mb-1">
              In-Process Cutting Force State (Pure Time-Series CRNN)
            </span>
            <div className="my-3">
              <span
                className={`inline-block px-4 py-1.5 rounded-full text-base font-black tracking-wide ${
                  !isConnected
                    ? 'bg-gray-100 text-gray-600 border border-gray-200'
                    : inference?.condition === 'DULLED'
                    ? 'bg-rose-100 text-rose-700 border border-rose-200 shadow-sm shadow-rose-500/10'
                    : inference?.condition === 'USED'
                    ? 'bg-amber-100 text-amber-800 border border-amber-200'
                    : 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                }`}
              >
                {!isConnected
                  ? 'AWAITING STREAM'
                  : inference?.condition === 'DULLED'
                  ? '🔴 CRITICAL FORCE ANOMALY'
                  : inference?.condition === 'USED'
                  ? '🟡 ELEVATED CUTTING LOAD'
                  : '🟢 NORMAL STABLE CUTTING'}
              </span>
            </div>
            <p className="text-xs text-gray-500">
              Model Diagnostic Confidence:{' '}
              <span className="font-mono font-bold text-gray-800">
                {isConnected && inference?.confidence ? `${inference.confidence}%` : '--'}
              </span>
            </p>
          </div>

          {/* Spindle Load & Machine Mechanical Telemetry */}
          <div className="p-6 bg-white border border-gray-200 rounded-xl shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-sm text-gray-900 flex items-center gap-1.5">
                <Gauge className="w-4 h-4 text-indigo-600" />
                <span>Spindle Motor Load</span>
              </h4>
              <span className="text-[10px] px-2 py-0.5 rounded bg-gray-100 text-gray-700 font-mono font-bold">
                Dynamometer
              </span>
            </div>

            <div className="flex items-baseline justify-center gap-1 py-1">
              <span
                className={`text-4xl font-mono font-black ${
                  !isConnected
                    ? 'text-gray-400'
                    : spindleLoadPct > 80
                    ? 'text-rose-600'
                    : spindleLoadPct > 55
                    ? 'text-amber-600'
                    : 'text-emerald-600'
                }`}
              >
                {isConnected ? spindleLoadPct : '--'}
              </span>
              <span className="text-gray-400 text-sm font-mono">% Rated Load</span>
            </div>

            {/* Load Progress Bar */}
            <div>
              <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden p-0.5 flex">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    !isConnected
                      ? 'bg-gray-300'
                      : spindleLoadPct > 80
                      ? 'bg-rose-500'
                      : spindleLoadPct > 55
                      ? 'bg-amber-500'
                      : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(100, spindleLoadPct)}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-gray-400 font-mono mt-1">
                <span>0%</span>
                <span>55% (Warning)</span>
                <span className="text-rose-500 font-bold">85% (Interlock Limit)</span>
              </div>
            </div>

            {/* Dynamic Stability & Chatter Diagnostic */}
            <div className="pt-3 border-t border-gray-100 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Cutting Vibration Stability:</span>
                <span
                  className={`px-2 py-0.5 rounded text-[11px] font-bold border font-mono ${stabilityStatus.color}`}
                >
                  {stabilityStatus.label}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-gray-500">Spindle Feed Status:</span>
                <span className="font-mono font-bold text-gray-800">
                  {!isConnected
                    ? 'STANDBY'
                    : isInterlockTripped
                    ? '0.00 mm/tooth (CUT)'
                    : '0.15 mm/tooth (ACTIVE)'}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-gray-500">Estimated Passes Until Check:</span>
                <span className="font-mono font-bold text-gray-900">
                  {isConnected && inference && inference.estimatedRemainingCycles !== null
                    ? `~${inference.estimatedRemainingCycles} Passes`
                    : '--'}
                </span>
              </div>
            </div>
          </div>

          {/* Quick Nav to Tool Verification Station */}
          <div className="p-5 bg-gradient-to-br from-indigo-50 to-indigo-100/50 border border-indigo-200 rounded-xl space-y-3">
            <h5 className="font-bold text-xs text-indigo-900 uppercase tracking-wider flex items-center gap-1.5">
              <ScanEye className="w-4 h-4 text-indigo-600" />
              <span>Tool Optical Verification Station</span>
            </h5>
            <p className="text-xs text-indigo-700 leading-relaxed">
              When cutting forces indicate tool wear or an E-STOP occurs, dismount the cutter to inspect
              the physical <strong>Flank Wear (Vb)</strong> and edge chipping under the high-resolution
              microscope in the Verification Station.
            </p>
            <button
              onClick={() => navigate(passIndex ? `/visual-qc?run=${passIndex}` : `/visual-qc`)}
              className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-lg shadow-sm transition flex items-center justify-center gap-1.5"
            >
              <ScanEye className="w-4 h-4" />
              <span>
                {passIndex !== null
                  ? `Open Tool Verification (Pass #${passIndex})`
                  : 'Open Tool Verification Station'}
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MachineMonitoringPage;
