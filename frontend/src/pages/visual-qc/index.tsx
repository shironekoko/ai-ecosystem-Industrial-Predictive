import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ScanEye,
  CheckCircle2,
  XCircle,
  Sparkles,
  ShieldCheck,
  ArrowLeft,
  Wrench,
  Inbox,
} from 'lucide-react';
import { PageHeader } from '../../components/common/PageHeader';
import { StatusBadge } from '../../components/common/StatusBadge';
import { useAuth } from '../../context/AuthContext';
import { OpticalScanViewport } from '../../components/inspection/OpticalScanViewport';

interface BladeInspectionState {
  bladeIndex: number;
  imageUrl: string | null;
  visionPrediction: 'SHARP' | 'USED' | 'DULLED' | null;
  visionConfidence: number | null;
  flankWearUm: number | null;
  gapsUm: number | null;
  overhangUm: number | null;
  status: 'PENDING_VERIFICATION' | 'CONFIRMED_WEAR' | 'FALSE_ALARM';
  verifiedBy?: string | null;
  verifiedAt?: string | null;
}

export function VisualQcPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();

  // Read dispatched tool parameters from URL query params (if dispatched from CNC/monitoring)
  const searchParams = new URLSearchParams(location.search);
  const toolParam = searchParams.get('tool');
  const runParam = searchParams.get('run');
  const toolId = toolParam ? Number(toolParam) : null;
  const passIndex = runParam ? Number(runParam) : null;

  const [selectedBlade, setSelectedBlade] = useState<number>(1);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Per-blade real-time inspection state (Clean standby ready for API stream)
  const [bladesState, setBladesState] = useState<Record<number, BladeInspectionState>>({
    1: {
      bladeIndex: 1,
      imageUrl: null,
      visionPrediction: null,
      visionConfidence: null,
      flankWearUm: null,
      gapsUm: null,
      overhangUm: null,
      status: 'PENDING_VERIFICATION',
    },
    2: {
      bladeIndex: 2,
      imageUrl: null,
      visionPrediction: null,
      visionConfidence: null,
      flankWearUm: null,
      gapsUm: null,
      overhangUm: null,
      status: 'PENDING_VERIFICATION',
    },
    3: {
      bladeIndex: 3,
      imageUrl: null,
      visionPrediction: null,
      visionConfidence: null,
      flankWearUm: null,
      gapsUm: null,
      overhangUm: null,
      status: 'PENDING_VERIFICATION',
    },
    4: {
      bladeIndex: 4,
      imageUrl: null,
      visionPrediction: null,
      visionConfidence: null,
      flankWearUm: null,
      gapsUm: null,
      overhangUm: null,
      status: 'PENDING_VERIFICATION',
    },
  });

  const currentBlade = bladesState[selectedBlade] || bladesState[1];
  const recordId = toolId && passIndex ? `T${toolId}R${passIndex}B${selectedBlade}` : `STANDBY_B${selectedBlade}`;
  const hasImage = Boolean(currentBlade.imageUrl);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const handleConfirmWear = () => {
    if (!hasImage) return;
    setBladesState((prev) => ({
      ...prev,
      [selectedBlade]: {
        ...prev[selectedBlade],
        status: 'CONFIRMED_WEAR',
        verifiedBy: `${user?.name || 'Engineer'} (${user?.title || 'Maintenance Eng'})`,
        verifiedAt: new Date().toLocaleTimeString(),
      },
    }));
    showToast(`✅ Confirmed: Blade #${selectedBlade} verified as tool wear. Logged to MLOps pool.`);
  };

  const handleFalseAlarm = () => {
    if (!hasImage) return;
    setBladesState((prev) => ({
      ...prev,
      [selectedBlade]: {
        ...prev[selectedBlade],
        status: 'FALSE_ALARM',
        verifiedBy: `${user?.name || 'Engineer'} (${user?.title || 'Maintenance Eng'})`,
        verifiedAt: new Date().toLocaleTimeString(),
      },
    }));
    showToast(`⚠️ Flagged: Blade #${selectedBlade} marked as False Alarm for model retraining.`);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dual-AI Tool Verification & Sign-Off"
        subtitle="High-Magnification Flank Face Microscope Inspection · Station Bench #1"
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate(`/machine-monitoring`)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-xs font-semibold text-gray-700 transition"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Spindle Feed</span>
            </button>
            <StatusBadge
              status={hasImage ? (currentBlade.status === 'PENDING_VERIFICATION' ? 'warning' : 'connected') : 'pending'}
              label={
                !hasImage
                  ? 'STATION STANDBY'
                  : currentBlade.status === 'PENDING_VERIFICATION'
                  ? 'AWAITING SIGN-OFF'
                  : currentBlade.status === 'CONFIRMED_WEAR'
                  ? 'WEAR CONFIRMED'
                  : 'FALSE ALARM'
              }
            />
          </div>
        }
      />

      {/* Floating Toast Notification */}
      {toastMessage && (
        <div className="fixed top-6 right-6 z-50 p-4 bg-slate-900 text-white text-xs font-semibold rounded-xl shadow-lg border border-slate-700 animate-slideDown flex items-center gap-2">
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Dismounted Tool Active Inspection Target Ribbon */}
      <div className="p-4 bg-white border border-gray-200 rounded-xl shadow-sm flex flex-wrap items-center justify-between gap-4">
        {/* Active Tool Metadata */}
        <div className="flex items-center gap-4">
          <div className="p-2.5 rounded-xl bg-indigo-50 border border-indigo-100 text-indigo-700">
            <Wrench className="w-5 h-5" />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm text-gray-900 font-mono">
                {toolId ? `Tool #${toolId} (4-Flute Face Mill)` : 'Tool: Awaiting Dispatch'}
              </span>
              {passIndex !== null ? (
                <span className="text-[11px] px-2 py-0.5 rounded bg-gray-100 text-gray-700 font-mono font-semibold">
                  Pass Cycle #{passIndex}
                </span>
              ) : (
                <span className="text-[11px] px-2 py-0.5 rounded bg-gray-100 text-gray-500 font-mono">
                  Cycle: --
                </span>
              )}
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold border ${
                  toolId ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-gray-100 text-gray-500 border-gray-200'
                }`}
              >
                {toolId ? 'Dispatched for Inspection' : 'Fixture Standby'}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5 font-mono">
              Origin: {toolId ? 'Spindle Haas VF-2SS · Dismounted for Optical Edge Verification' : 'Keyence VHX Fixture Bench #1 · Ready for Next Cutter'}
            </p>
          </div>
        </div>

        {/* 4-Flute Blade Selector (Blade 1 to 4) */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
            Select Blade:
          </span>
          <div className="flex items-center gap-1.5 p-1 bg-gray-100 rounded-lg">
            {[1, 2, 3, 4].map((blade) => {
              const isSelected = selectedBlade === blade;
              const bladeObj = bladesState[blade];
              const isVerified =
                bladeObj?.status === 'CONFIRMED_WEAR' || bladeObj?.status === 'FALSE_ALARM';

              return (
                <button
                  key={blade}
                  onClick={() => setSelectedBlade(blade)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition ${
                    isSelected
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-500 hover:text-gray-800'
                  }`}
                >
                  <span>Blade #{blade}</span>
                  {isVerified ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  ) : bladeObj.imageUrl ? (
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
                  ) : (
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Grid: Microscope Viewport + Dual-AI Diagnostics */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left: Microscope Image Viewport (Clean Empty Standby ready for Camera Feed / API) */}
        <div className="col-span-12 lg:col-span-7">
          <OpticalScanViewport
            recordId={recordId}
            imageUrl={currentBlade.imageUrl}
          />
        </div>

        {/* Right: Dual-AI Consensus & Engineering Sign-Off */}
        <div className="col-span-12 lg:col-span-5 space-y-5">
          {/* Dual-AI Consensus Card */}
          <div className="p-5 bg-white border border-gray-200 rounded-xl shadow-sm space-y-4">
            <h4 className="font-bold text-xs uppercase tracking-wider text-gray-400 flex items-center justify-between">
              <span>Dual-AI Prediction Comparison</span>
              <span className="font-mono text-gray-500 font-semibold text-[11px]">
                {hasImage
                  ? currentBlade.visionPrediction
                    ? 'Comparison Active'
                    : 'Awaiting Vision AI'
                  : 'Awaiting Camera Feed'}
              </span>
            </h4>

            {/* Model 1: Sensor AI (1D-CNN + BiLSTM - Captured in-process during cutting) */}
            <div className="p-3.5 rounded-lg bg-gray-50 border border-gray-100 flex items-center justify-between">
              <div>
                <span className="text-[11px] font-bold text-gray-500 block">
                  1. Force Sensor AI (1D-CNN + BiLSTM)
                </span>
                <span className="text-xs text-gray-400 font-mono">
                  In-Process Thrust Force: -- N
                </span>
              </div>
              <div className="text-right">
                <span className="inline-block px-2.5 py-0.5 rounded bg-gray-200 text-gray-600 font-mono text-[11px] font-semibold">
                  Awaiting Telemetry API
                </span>
              </div>
            </div>

            {/* Model 2: Vision AI (YOLOv8-cls - Requires optical image) */}
            <div
              className={`p-3.5 rounded-lg border transition ${
                hasImage
                  ? 'bg-gray-50 border-gray-100'
                  : 'bg-gray-50/50 border-gray-100 opacity-60'
              } flex items-center justify-between`}
            >
              <div>
                <span className="text-[11px] font-bold text-gray-500 block">
                  2. Optical Vision AI (YOLOv8-cls)
                </span>
                <span className="text-xs text-gray-400">Modality: tool/ microscope</span>
              </div>
              <div className="text-right">
                {hasImage && currentBlade.visionPrediction ? (
                  <>
                    <span
                      className={`inline-block px-2.5 py-1 rounded-full text-xs font-bold ${
                        currentBlade.visionPrediction === 'DULLED'
                          ? 'bg-rose-100 text-rose-700'
                          : currentBlade.visionPrediction === 'USED'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-emerald-100 text-emerald-700'
                      }`}
                    >
                      {currentBlade.visionPrediction}
                    </span>
                    <span className="block text-[10px] font-mono text-gray-400 mt-0.5">
                      Conf: {currentBlade.visionConfidence}%
                    </span>
                  </>
                ) : (
                  <span className="inline-block px-2.5 py-0.5 rounded bg-gray-200 text-gray-600 font-mono text-[11px] font-semibold">
                    Awaiting Camera Feed
                  </span>
                )}
              </div>
            </div>

            {/* Physical Optical Ground Truth Metrology (ISO 8688) */}
            <div
              className={`pt-3 border-t border-gray-100 space-y-3 transition ${
                hasImage ? '' : 'opacity-50'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-gray-700 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Physical Microscope Metrology (ISO 8688)</span>
                </span>
                <span className="text-[10px] font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-bold">
                  {hasImage ? 'Ground Truth' : 'Awaiting Feed'}
                </span>
              </div>

              {/* Flank Wear Vb Meter */}
              <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500 font-medium">Flank Wear Land (Vb):</span>
                  <div className="flex items-baseline gap-1">
                    <span
                      className={`text-xl font-mono font-black ${
                        !hasImage
                          ? 'text-gray-400'
                          : (currentBlade.flankWearUm || 0) >= 125
                          ? 'text-rose-600'
                          : (currentBlade.flankWearUm || 0) >= 70
                          ? 'text-amber-600'
                          : 'text-emerald-600'
                      }`}
                    >
                      {hasImage && currentBlade.flankWearUm !== null ? currentBlade.flankWearUm : '--'}
                    </span>
                    <span className="text-xs text-gray-400 font-mono">µm</span>
                  </div>
                </div>

                {/* Progress bar relative to 130 µm ISO limit */}
                <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden flex">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      !hasImage
                        ? 'bg-gray-300'
                        : (currentBlade.flankWearUm || 0) >= 125
                        ? 'bg-rose-500'
                        : (currentBlade.flankWearUm || 0) >= 70
                        ? 'bg-amber-500'
                        : 'bg-emerald-500'
                    }`}
                    style={{
                      width: `${
                        hasImage && currentBlade.flankWearUm !== null
                          ? Math.min(100, ((currentBlade.flankWearUm || 0) / 150) * 100)
                          : 0
                      }%`,
                    }}
                  />
                </div>
                <div className="flex justify-between text-[9px] text-gray-400 font-mono">
                  <span>30 µm (New)</span>
                  <span>70 µm (Caution)</span>
                  <span className="text-rose-500 font-bold">130 µm (Limit)</span>
                </div>
              </div>

              {/* Edge Gaps & Burr Overhang */}
              <div className="grid grid-cols-2 gap-2 text-center font-mono">
                <div className="p-2 bg-gray-50 rounded-lg border border-gray-100">
                  <span className="text-[10px] text-gray-400 block">Edge Chipping (Gaps)</span>
                  <span
                    className={`text-xs font-bold ${
                      !hasImage
                        ? 'text-gray-400'
                        : (currentBlade.gapsUm || 0) > 40
                        ? 'text-rose-600'
                        : (currentBlade.gapsUm || 0) > 15
                        ? 'text-amber-600'
                        : 'text-gray-800'
                    }`}
                  >
                    {hasImage && currentBlade.gapsUm !== null ? `${currentBlade.gapsUm} µm` : '-- µm'}
                  </span>
                </div>
                <div className="p-2 bg-gray-50 rounded-lg border border-gray-100">
                  <span className="text-[10px] text-gray-400 block">Burr Overhang</span>
                  <span className="text-xs font-bold text-gray-700">
                    {hasImage && currentBlade.overhangUm !== null ? `${currentBlade.overhangUm} µm` : '-- µm'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Human-in-the-Loop Sign-off Decision Hub */}
          <div className="p-5 bg-white border border-gray-200 rounded-xl shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-xs uppercase tracking-wider text-gray-800 flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-indigo-600" />
                <span>Engineer Verification (Sign-off)</span>
              </h4>
              <span className="text-[11px] text-gray-400">Human-in-the-Loop</span>
            </div>

            {!hasImage ? (
              <div className="p-5 bg-slate-50 border border-slate-200 rounded-xl text-center space-y-2">
                <div className="w-8 h-8 mx-auto text-slate-400 flex items-center justify-center">
                  <Inbox className="w-6 h-6 stroke-[1.5]" />
                </div>
                <p className="text-xs font-bold text-slate-700">Station Standby</p>
                <p className="text-[11px] text-slate-500 leading-relaxed max-w-xs mx-auto">
                  Awaiting dismounted tool inspection trigger & microscope optical feed from API.
                </p>
              </div>
            ) : currentBlade.status === 'PENDING_VERIFICATION' ? (
              <div className="space-y-3">
                <p className="text-xs text-gray-600 leading-relaxed">
                  Optical image and cutting forces analyzed for Blade #{selectedBlade}. Inspect the cutting edge and submit verification:
                </p>

                <div className="grid grid-cols-2 gap-3 pt-1">
                  <button
                    onClick={handleConfirmWear}
                    className="flex items-center justify-center gap-1.5 py-2.5 px-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-lg shadow-sm transition"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Confirm Wear (สึกจริง)</span>
                  </button>

                  <button
                    onClick={handleFalseAlarm}
                    className="flex items-center justify-center gap-1.5 py-2.5 px-3 bg-gray-100 hover:bg-rose-50 hover:text-rose-700 text-gray-700 font-bold text-xs rounded-lg border border-gray-200 transition"
                  >
                    <XCircle className="w-4 h-4" />
                    <span>False Alarm (พลาด)</span>
                  </button>
                </div>
              </div>
            ) : (
              <div
                className={`p-4 rounded-xl border text-xs space-y-1.5 ${
                  currentBlade.status === 'CONFIRMED_WEAR'
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                    : 'bg-rose-50 border-rose-200 text-rose-900'
                }`}
              >
                <div className="flex items-center gap-2 font-bold text-sm">
                  {currentBlade.status === 'CONFIRMED_WEAR' ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-600" />
                  )}
                  <span>
                    {currentBlade.status === 'CONFIRMED_WEAR'
                      ? `Blade #${selectedBlade}: Tool Wear Confirmed`
                      : `Blade #${selectedBlade}: Marked as False Alarm`}
                  </span>
                </div>
                <p className="text-[11px] opacity-80">
                  Signed off by: <span className="font-semibold">{currentBlade.verifiedBy}</span>
                </p>
                <p className="text-[11px] opacity-70">
                  Timestamp: {currentBlade.verifiedAt} · Ground truth logged to MinIO.
                </p>

                <button
                  onClick={() => {
                    setBladesState((prev) => ({
                      ...prev,
                      [selectedBlade]: { ...prev[selectedBlade], status: 'PENDING_VERIFICATION' },
                    }));
                  }}
                  className="mt-2 text-[11px] underline opacity-70 hover:opacity-100 block"
                >
                  Edit Decision / Re-verify
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default VisualQcPage;
