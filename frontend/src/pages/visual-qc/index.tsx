import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ScanEye,
  CheckCircle2,
  XCircle,
  Sparkles,
  ShieldCheck,
  ArrowLeft,
  Wrench,
  AlertTriangle,
  Database,
  Layers,
  Activity,
  Check,
} from 'lucide-react';
import { PageHeader } from '../../components/common/PageHeader';
import { StatusBadge } from '../../components/common/StatusBadge';
import { useAuth } from '../../context/AuthContext';
import { OpticalScanViewport, ViewportModality } from '../../components/inspection/OpticalScanViewport';
import { api, BladeQCData } from '../../services/api';

export function VisualQcPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();

  // Read dispatched tool parameters from URL query params
  const searchParams = new URLSearchParams(location.search);
  const toolParam = searchParams.get('tool');
  const runParam = searchParams.get('run');
  const toolId = toolParam ? Number(toolParam) : 10;

  const [activePassIndex, setActivePassIndex] = useState<number>(() => {
    return runParam ? Number(runParam) : 11;
  });
  const [machineStatus, setMachineStatus] = useState<{
    status: string;
    isStopped: boolean;
    currentRun: number;
    stoppedRun?: number;
    stopReason?: string;
  } | null>(null);

  // Sync with machine status if no explicit run parameter is in URL
  useEffect(() => {
    api.getMachineStatus().then((ms) => {
      if (ms) {
        setMachineStatus(ms);
        if (!runParam) {
          if (ms.isStopped && ms.stoppedRun) {
            setActivePassIndex(ms.stoppedRun);
          } else if (ms.currentRun) {
            setActivePassIndex(ms.currentRun);
          }
        }
      }
    });
  }, [runParam]);

  const passIndex = activePassIndex;

  const [selectedBlade, setSelectedBlade] = useState<number>(1);
  const [activeModality, setActiveModality] = useState<ViewportModality>('TOOL_EDGE_PROCESSED');
  const [qcData, setQcData] = useState<BladeQCData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Per-blade verification sign-off cache
  const [verifiedBlades, setVerifiedBlades] = useState<Record<number, {
    status: 'CONFIRMED_WEAR' | 'RETRAIN_FLAGGED';
    verifiedBy: string;
    verifiedAt: string;
    message: string;
  }>>({});

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4500);
  };

  // Fetch QC data for the selected blade
  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    api.getBladeQc(toolId, passIndex, selectedBlade).then((data) => {
      if (!isMounted) return;
      if (data) {
        setQcData(data);
        if (data.status === 'CONFIRMED_WEAR' || data.status === 'RETRAIN_FLAGGED') {
          setVerifiedBlades((prev) => ({
            ...prev,
            [selectedBlade]: {
              status: data.status as any,
              verifiedBy: data.verifiedBy || 'Maintenance Engineer',
              verifiedAt: data.verifiedAt || new Date().toLocaleTimeString(),
              message: data.status === 'CONFIRMED_WEAR'
                ? 'Tool replacement confirmed.'
                : 'Flagged for Active Learning retraining.',
            },
          }));
        }
      } else {
        // Fallback simulation based on run index
        const isDulled = passIndex >= 12;
        setQcData({
          recordId: `T${toolId}R${passIndex}B${selectedBlade}`,
          imageUrl: `/api/v1/qc/images/tool/T${toolId}R${passIndex}B${selectedBlade}.jpg`,
          chipImageUrl: `/api/v1/qc/images/chip/T${toolId}R${passIndex}B${selectedBlade}.jpg`,
          toolImageUrl: `/api/v1/qc/images/tool/T${toolId}R${passIndex}B${selectedBlade}.jpg`,
          toolProcessedImageUrl: `/api/v1/qc/images/tool-processed/T${toolId}R${passIndex}B${selectedBlade}.jpg`,
          gradCamUrl: `/api/v1/qc/gradcam/T${toolId}R${passIndex}B${selectedBlade}.jpg`,
          tier1ForceAlert: {
            condition: isDulled ? 'DULLED' : 'USED',
            confidence: 0.92,
            flankWearEstimateUm: isDulled ? 134.5 : 88.0,
            triggerMetric: 'Fres > 210 N',
            status: 'ALERT',
          },
          tier2ChipAi: {
            condition: isDulled ? 'DULLED' : 'USED',
            confidence: 0.94,
            chipImageUrl: `/api/v1/qc/images/chip/T${toolId}R${passIndex}B${selectedBlade}.jpg`,
            morphologyAnalysis: 'Segmented shear bands with thermal discoloration',
            curlContinuity: isDulled ? 'DISCONTINUOUS_BRITTLE' : 'SEGMENTED',
            surfaceRoughnessIndex: isDulled ? 4.8 : 2.5,
          },
          tier3ToolEdge: {
            toolImageUrl: `/api/v1/qc/images/tool/T${toolId}R${passIndex}B${selectedBlade}.jpg`,
            processedImageUrl: `/api/v1/qc/images/tool-processed/T${toolId}R${passIndex}B${selectedBlade}.jpg`,
            flankWearUm: isDulled ? 135.2 : 88.4,
            gapsUm: isDulled ? 18.4 : 6.2,
            overhangUm: isDulled ? 14.1 : 7.0,
            chippingDetected: isDulled,
            isoLimitExceeded: isDulled,
            edgeIntegrityScore: isDulled ? 38.5 : 72.0,
            opticalVerdict: isDulled ? 'DULLED' : 'USED',
          },
          consensus: {
            isAgreement: true,
            discrepancyType: 'NONE',
            consensusVerdict: isDulled ? 'CONFIRMED_WEAR' : 'CUTTER_NORMAL',
            recommendedAction: isDulled ? 'REPLACE_TOOL' : 'CONTINUE_CUTTING',
            rationale: 'Physical edge inspection confirms flank wear exceeding ISO limit.',
          },
          visionPrediction: isDulled ? 'DULLED' : 'USED',
          visionConfidence: 0.94,
          flankWearUm: isDulled ? 135.2 : 88.4,
          gapsUm: isDulled ? 18.4 : 6.2,
          overhangUm: isDulled ? 14.1 : 7.0,
          status: 'PENDING_VERIFICATION',
        });
      }
      setLoading(false);
    });

    return () => {
      isMounted = false;
    };
  }, [toolId, passIndex, selectedBlade]);

  const currentVerified = verifiedBlades[selectedBlade];
  const recordId = `T${toolId}R${passIndex}B${selectedBlade}`;

  // Image Processing Ground Truth Values
  const flankWear = qcData?.tier3ToolEdge.flankWearUm ?? 0;
  const gaps = qcData?.tier3ToolEdge.gapsUm ?? 0;
  const overhang = qcData?.tier3ToolEdge.overhangUm ?? 0;
  const isBrokenOrWorn = flankWear >= 130.0 || gaps > 15.0;

  // Active Retraining Queue State
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [activeRetrainJob, setActiveRetrainJob] = useState<{
    jobId: string;
    modelName: string;
    correctedLabel: string;
    chipImage: string;
    userAnswer: string;
    status: 'QUEUED' | 'IN_PROGRESS' | 'COMPLETED';
    progressMsg?: string;
  } | null>(null);

  // Human-in-the-Loop Decision Handler
  // Triggers YOLOv8 Vision Retraining immediately if the human overrides DULLED to SHARP or USED
  // Retrain คือการนำภาพจาก chip/ ร่วมกับคำตอบที่ผู้ใช้ระบุเป็น Ground Truth
  const handleHumanSignOff = async (actualCondition: 'SHARP' | 'USED' | 'DULLED') => {
    setIsSubmitting(true);
    const engineerName = user?.name ? `${user.name} (QC Inspector)` : 'Senior Tooling Engineer';
    const isDiscrepancy = actualCondition === 'SHARP' || actualCondition === 'USED';
    const decision = isDiscrepancy ? 'SEND_TO_RETRAIN' : 'CONFIRMED_WEAR';

    try {
      const res = await api.submitVerification(
        recordId,
        toolId,
        passIndex,
        selectedBlade,
        decision,
        isDiscrepancy
          ? `Human-in-the-Loop: Model predicted DULLED, but inspection confirms blade is actually ${actualCondition}.`
          : 'Human inspection confirmed wear (DULLED).',
        engineerName,
        actualCondition
      );

      const nowTime = new Date().toLocaleTimeString();
      setVerifiedBlades((prev) => ({
        ...prev,
        [selectedBlade]: {
          status: isDiscrepancy ? 'RETRAIN_FLAGGED' : 'CONFIRMED_WEAR',
          verifiedBy: engineerName,
          verifiedAt: nowTime,
          message: isDiscrepancy
            ? `โมเดลบอก DULLED แต่มีดจริงเป็น ${actualCondition} ➔ ดึงภาพ chip/${recordId}.jpg คู่กับคำตอบส่งคิว Retrain YOLOv8 ทันที!`
            : 'มีดพังจริง (DULLED): อนุมัติคำสั่งเปลี่ยนหัวมีดใหม่',
        },
      }));

      if (res?.autoRetrainTriggered && res?.retrainJobId) {
        const chipImg = res.chipImageRetrained || `chip/${recordId}.jpg`;
        const userAns = res.userAnswer || actualCondition;

        setActiveRetrainJob({
          jobId: res.retrainJobId,
          modelName: res.modelRetrained || 'yolov8_chip_wear',
          correctedLabel: actualCondition,
          chipImage: chipImg,
          userAnswer: userAns,
          status: 'QUEUED',
          progressMsg: `นำภาพจาก ${chipImg} คู่กับคำตอบของผู้ใช้ ('${userAns}') เข้าคิว ARQ Worker เรียบร้อย กำลังเริ่ม Fine-tune YOLOv8 Vision...`,
        });

        showToast(`🚀 นำภาพ ${chipImg} + คำตอบ [${userAns}] สั่ง Retrain YOLOv8 ทันที! (Job ID: ${res.retrainJobId.slice(0, 14)})`);

        // Poll retrain status
        const pollTimer = window.setInterval(async () => {
          try {
            const statusRes = await api.getRetrainStatus(res.retrainJobId);
            if (statusRes.status === 'complete') {
              clearInterval(pollTimer);
              setActiveRetrainJob((prev) => prev ? {
                ...prev,
                status: 'COMPLETED',
                progressMsg: statusRes.result || `Retrain โมเดล YOLOv8 บนภาพ ${chipImg} ด้วยคำตอบ [${userAns}] สำเร็จ!`,
              } : null);
              showToast('🎉 Retrain YOLOv8 Vision อัปเกรดสำเร็จ!');
            } else if (statusRes.status === 'in_progress') {
              setActiveRetrainJob((prev) => prev ? {
                ...prev,
                status: 'IN_PROGRESS',
                progressMsg: `กำลังเทรน Epochs โมเดล YOLOv8 บนภาพ ${chipImg} คู่กับคำตอบ [${userAns}]...`,
              } : null);
            }
          } catch {
            // ignore
          }
        }, 3000);
      } else {
        showToast('✅ ยืนยันมีดพังจริง (DULLED) เรียบร้อย: อนุมัติเปลี่ยนหัวมีด');
      }
    } catch (err: any) {
      showToast(`⚠️ เกิดข้อผิดพลาดในการบันทึก: ${err.message || 'Error'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tool Physical Verification Bench (Flank Wear Vb Inspection)"
        subtitle="ตรวจเช็คภาพคมมีดจริงที่วิศวกรแกะออกมาด้วย Image Processing หาค่า Vb และรอยบิ่น เพื่อยืนยันว่าพังจริงไหม"
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
              status={
                currentVerified?.status === 'CONFIRMED_WEAR'
                  ? 'connected'
                  : currentVerified?.status === 'RETRAIN_FLAGGED'
                  ? 'warning'
                  : 'pending'
              }
              label={
                currentVerified?.status === 'CONFIRMED_WEAR'
                  ? 'WEAR CONFIRMED · REPLACE TOOL'
                  : currentVerified?.status === 'RETRAIN_FLAGGED'
                  ? 'FALSE ALARM · RETRAIN QUEUED'
                  : 'AWAITING PHYSICAL BENCH SIGN-OFF'
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

      {/* Dynamic Bench State Banner */}
      {machineStatus?.isStopped ? (
        <div className="p-4 bg-gradient-to-r from-slate-900 to-rose-950 text-white rounded-xl shadow-sm border border-rose-900/60 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-rose-500/20 border border-rose-500/40 text-rose-300">
              <Activity className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-rose-500/30 border border-rose-500/50 text-rose-200 font-bold">
                  🛑 Safety Interlock Triggered · Spindle Stopped
                </span>
                <span className="text-xs text-slate-300 font-mono">
                  Tool #{toolId} · Milling Pass #{passIndex}
                </span>
              </div>
              <p className="text-xs text-slate-200 mt-1">
                สปินเดิลตัดการทำงานฉุกเฉิน: โมเดลตรวจพบมีดสึกหรอวิกฤต (DULLED) ที่รอบตัด Pass #{passIndex} จึงสั่งหยุดเครื่องและถอดหัวมีดมาตรวจสอบที่แท่นส่องกล้อง
              </p>
            </div>
          </div>
          <div className="text-right font-mono text-xs text-slate-400">
            <span>Station: </span>
            <strong className="text-white">Bench #1 (Keyence VHX Optical Fixture)</strong>
          </div>
        </div>
      ) : (
        <div className="p-4 bg-gradient-to-r from-slate-900 to-indigo-950 text-white rounded-xl shadow-sm border border-slate-800 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-indigo-500/20 border border-indigo-400/30 text-indigo-300">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 font-bold">
                  🟢 Bench Standby — ยังไม่มีหัวมีดถูกถอดมาตรวจ
                </span>
              </div>
              <p className="text-xs text-slate-200 mt-1">
                เมื่อระบบ Safety Interlock ตรวจพบ DULLED มีดจะถูกส่งมาตรวจที่แท่นนี้อัตโนมัติ
              </p>
              <p className="text-xs text-slate-400 mt-1">
                (ดูข้อมูลย้อนหลัง: สามารถเลือก Pass ที่ผ่านมาแล้วจากเมนูด้านล่างเพื่อดูประวัติได้)
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 font-mono text-xs">
            <button
              onClick={() => navigate('/machine-monitoring')}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition"
            >
              เปิดดูสตรีมที่ Machine Monitoring
            </button>
          </div>
        </div>
      )}

      {/* Dismounted Tool Flute Selector Ribbon */}
      <div className="p-4 bg-white border border-gray-200 rounded-xl shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-slate-100 border border-slate-200 text-slate-700">
            <Wrench className="w-5 h-5" />
          </div>
          <div>
            <span className="font-bold text-sm text-gray-900 font-mono">
              Target Flute Scan: <strong className="text-indigo-600">{recordId}</strong>
            </span>
            <p className="text-xs text-gray-500 font-mono">
              4-Flute Face Mill Insert · Microscope Resolution 1550×500 px
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          {/* Pass Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
              Milling Pass:
            </span>
            <select
              value={passIndex}
              onChange={(e) => setActivePassIndex(Number(e.target.value))}
              className="px-2.5 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-xs font-mono font-bold text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
            >
              {Array.from({ length: 14 }, (_, i) => i + 1).map((p) => (
                <option key={p} value={p}>
                  Pass #{p} {p >= 11 ? '(Dulled Stage)' : p >= 7 ? '(Used Stage)' : '(Sharp Stage)'}
                </option>
              ))}
            </select>
          </div>

          {/* 4-Flute Blade Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
              Blade:
            </span>
            <div className="flex items-center gap-1.5 p-1 bg-gray-100 rounded-lg">
              {[1, 2, 3, 4].map((blade) => {
                const isSelected = selectedBlade === blade;
                const isConfirmed = verifiedBlades[blade]?.status === 'CONFIRMED_WEAR';
                const isRetrain = verifiedBlades[blade]?.status === 'RETRAIN_FLAGGED';

                return (
                  <button
                    key={blade}
                    onClick={() => setSelectedBlade(blade)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition ${
                      isSelected
                        ? 'bg-white text-gray-900 shadow-xs'
                        : 'text-gray-500 hover:text-gray-800'
                    }`}
                  >
                    <span>Blade #{blade}</span>
                    {isConfirmed ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    ) : isRetrain ? (
                      <Database className="w-3.5 h-3.5 text-amber-600" />
                    ) : (
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Microscope Viewport + Optical Vb Metrology & Consensus Sign-Off */}
      {(!machineStatus?.isStopped && passIndex >= (machineStatus?.currentRun || 1)) ? (
        <div className="flex flex-col items-center justify-center p-12 bg-white rounded-xl border border-gray-200 border-dashed text-gray-400">
          <ScanEye className="w-12 h-12 mb-3 text-gray-300" />
          <h3 className="text-lg font-bold text-gray-500">Standby Mode</h3>
          <p className="text-sm">ไม่มีข้อมูลการตรวจสอบคมมีดสำหรับ Pass ปัจจุบัน (เครื่องยังทำงานอยู่)</p>
        </div>
      ) : (
        <div className="grid grid-cols-12 gap-6">
          {/* Left Column: Physical Tool Flank Microscope Viewport */}
          <div className="col-span-12 lg:col-span-7">
            <OpticalScanViewport
            recordId={recordId}
            toolImageUrl={qcData?.toolImageUrl}
            toolProcessedImageUrl={qcData?.toolProcessedImageUrl}
            activeModality={activeModality}
            onModalityChange={setActiveModality}
          />
        </div>

        {/* Right Column: Optical Metrology & Sign-Off Hub */}
        <div className="col-span-12 lg:col-span-5 space-y-5">
          {/* Card 1: Optical Edge Metrology (ISO 8688-2) */}
          <div className="p-5 bg-white border border-gray-200 rounded-xl shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <span className="font-bold text-xs uppercase tracking-wider text-purple-700 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-purple-600" />
                <span>Optical Wear Metrology (การวัดขนาดคมมีด Vb จากภาพกำลังขยาย)</span>
              </span>
              <span className="text-[10px] font-mono bg-purple-50 text-purple-700 border border-purple-200 px-2 py-0.5 rounded font-bold">
                ISO 8688-2 Measurement
              </span>
            </div>

            {/* Explanation Note for Operators */}
            <p className="text-[11px] text-gray-500 leading-relaxed bg-gray-50 p-2.5 rounded-lg border border-gray-100">
              🔬 ระบบประมวลผลภาพ (OpenCV Contour Analysis) ตรวจวัดระยะความกว้างของรอยสึกหรอด้านข้าง (Flank Wear Land) จากภาพถ่ายกล้องจุลทรรศน์จริง เพื่อเป็นข้อมูลมาตรวิทยาช่วยวิศวกรยืนยันสภาพมีดจริงก่อนกด Sign-Off
            </p>

            {/* Flank Wear Land Vb Gauge */}
            <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-100 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-600 font-medium">Flank Wear Land (Vb):</span>
                <div className="flex items-baseline gap-1">
                  <span
                    className={`text-2xl font-mono font-black ${
                      flankWear >= 130
                        ? 'text-rose-600'
                        : flankWear >= 70
                        ? 'text-amber-600'
                        : 'text-emerald-600'
                    }`}
                  >
                    {flankWear}
                  </span>
                  <span className="text-xs text-gray-400 font-mono">µm</span>
                </div>
              </div>

              {/* Progress bar relative to 130 µm ISO limit */}
              <div className="w-full h-2.5 bg-gray-200 rounded-full overflow-hidden flex">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    flankWear >= 130
                      ? 'bg-rose-500'
                      : flankWear >= 70
                      ? 'bg-amber-500'
                      : 'bg-emerald-500'
                  }`}
                  style={{
                    width: `${Math.min(100, (flankWear / 150) * 100)}%`,
                  }}
                />
              </div>
              <div className="flex justify-between text-[9px] text-gray-400 font-mono">
                <span>30 µm (คมปกติ)</span>
                <span>70 µm (เริ่มสึก)</span>
                <span className="text-rose-600 font-bold">130 µm (เกณฑ์ขีดจำกัด ISO)</span>
              </div>
            </div>

            {/* Edge Chipping Gaps & Burr Overhang */}
            <div className="grid grid-cols-2 gap-2 text-center font-mono">
              <div className="p-2.5 bg-gray-50 rounded-lg border border-gray-100">
                <span className="text-[10px] text-gray-400 block uppercase">Chipping Gaps (รอยบิ่น)</span>
                <span
                  className={`text-xs font-bold ${
                    gaps > 15 ? 'text-rose-600' : 'text-emerald-600'
                  }`}
                >
                  {gaps} µm {gaps > 15 ? '(ตรวจพบรอยบิ่น)' : '(ขอบคมต่อเนื่อง)'}
                </span>
              </div>
              <div className="p-2.5 bg-gray-50 rounded-lg border border-gray-100">
                <span className="text-[10px] text-gray-400 block uppercase">Burr Overhang</span>
                <span className="text-xs font-bold text-gray-700">
                  {overhang} µm
                </span>
              </div>
            </div>
          </div>

          {/* Card 2: Human-in-the-Loop Verification & Automated Retraining Hub */}
          <div className="p-5 bg-white border border-gray-200 rounded-xl shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-xs uppercase tracking-wider text-gray-800 flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-indigo-600" />
                <span>Human-in-the-Loop Inspection</span>
              </h4>
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                  currentVerified?.status === 'CONFIRMED_WEAR'
                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                    : currentVerified?.status === 'RETRAIN_FLAGGED'
                    ? 'bg-amber-100 text-amber-800 border border-amber-200'
                    : 'bg-rose-50 text-rose-700 border border-rose-200 animate-pulse'
                }`}
              >
                {currentVerified?.status === 'CONFIRMED_WEAR'
                  ? 'VERIFIED: WEAR CONFIRMED'
                  : currentVerified?.status === 'RETRAIN_FLAGGED'
                  ? 'AUTO-RETRAIN ENQUEUED'
                  : 'AI PREDICTION: DULLED'}
              </span>
            </div>

            {/* AI Prediction Context */}
            <div className="p-3 bg-slate-900 rounded-xl border border-slate-800 text-white flex items-center justify-between text-xs font-mono">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-rose-400" />
                <span className="text-slate-300">YOLOv8 Vision Prediction:</span>
              </div>
              <span className={`px-2 py-0.5 rounded font-bold border ${
                qcData?.tier2ChipAi.condition === 'DULLED' ? 'bg-rose-500/20 text-rose-300 border-rose-500/40' :
                qcData?.tier2ChipAi.condition === 'USED' ? 'bg-amber-500/20 text-amber-300 border-amber-500/40' :
                'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
              }`}>
                {qcData?.tier2ChipAi.condition ?? 'N/A'} ({( (qcData?.tier2ChipAi.confidence ?? 0) * 100 ).toFixed(1)}% Conf)
              </span>
            </div>

            {/* Live Auto-Retraining Status Banner if Discrepancy Triggered */}
            {activeRetrainJob && (
              <div className="p-4 rounded-xl border bg-gradient-to-br from-indigo-50 to-purple-50 border-indigo-200 space-y-2.5 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-indigo-950 flex items-center gap-1.5">
                    <Database className="w-4 h-4 text-indigo-600" />
                    <span>YOLOv8 Vision Retraining Queue (Active)</span>
                  </span>
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded font-black ${
                      activeRetrainJob.status === 'COMPLETED'
                        ? 'bg-emerald-600 text-white'
                        : 'bg-indigo-600 text-white animate-pulse'
                    }`}
                  >
                    {activeRetrainJob.status === 'COMPLETED' ? 'RETRAIN COMPLETED' : 'TRAINING IN PROGRESS'}
                  </span>
                </div>
                <div className="text-[11px] font-mono text-indigo-900 space-y-1.5">
                  <div className="flex justify-between">
                    <span>Job ID:</span>
                    <span className="font-bold">{activeRetrainJob.jobId}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Retrain Input Image:</span>
                    <span className="font-bold text-indigo-800 bg-white px-2 py-0.5 rounded border border-indigo-200">
                      {activeRetrainJob.chipImage}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Ground Truth (คำตอบผู้ใช้):</span>
                    <span className="font-bold text-rose-700 bg-white px-2 py-0.5 rounded border border-rose-200">
                      {activeRetrainJob.userAnswer} (แก้จาก DULLED)
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Target Vision Model:</span>
                    <span className="font-bold">{activeRetrainJob.modelName}</span>
                  </div>
                </div>
                <p className="text-[11px] text-indigo-700 pt-1 border-t border-indigo-100/80">
                  {activeRetrainJob.progressMsg}
                </p>
              </div>
            )}

            {/* Human Verification Action Buttons */}
            <div className="space-y-2 pt-1">
              <span className="text-[11px] font-bold text-gray-700 uppercase tracking-wider block">
                คำตัดสินของวิศวกรผู้เชี่ยวชาญ (Human-in-the-Loop Sign-off):
              </span>

              {/* Option A: Confirm */}
              <button
                disabled={isSubmitting}
                onClick={() => handleHumanSignOff(qcData?.tier2ChipAi.condition as any)}
                className="w-full p-2.5 rounded-xl border border-gray-200 hover:border-emerald-400 bg-white hover:bg-emerald-50/50 text-left transition flex items-center justify-between group shadow-xs cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 group-hover:scale-110 transition" />
                  <div>
                    <span className="text-xs font-bold text-gray-900 block">
                      โมเดลทำนาย {qcData?.tier2ChipAi.condition} — ฉันเห็นด้วย (ยืนยัน)
                    </span>
                    <span className="text-[10px] text-gray-500 font-mono">
                      ไม่ต้องส่ง Retrain
                    </span>
                  </div>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-100 text-gray-600 group-hover:bg-emerald-100 group-hover:text-emerald-800 font-bold">
                  Approve
                </span>
              </button>

              {/* Option B: Discrepancy 1 (Triggers YOLOv8 Retrain) */}
              <button
                disabled={isSubmitting}
                onClick={() => handleHumanSignOff(qcData?.tier2ChipAi.condition === 'SHARP' ? 'USED' : 'SHARP')}
                className="w-full p-2.5 rounded-xl border border-amber-200 hover:border-amber-400 bg-amber-50/50 hover:bg-amber-100/60 text-left transition flex items-center justify-between group shadow-xs cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-amber-600 group-hover:scale-110 transition" />
                  <div>
                    <span className="text-xs font-bold text-amber-950 block">
                      โมเดลบอก {qcData?.tier2ChipAi.condition} แต่มีดจริงเป็น [ {qcData?.tier2ChipAi.condition === 'SHARP' ? 'USED' : 'SHARP'} ]
                    </span>
                    <span className="text-[10px] text-amber-700 font-mono">
                      ⚡ ดึงภาพ chip/{recordId}.jpg คู่กับคำตอบ [ {qcData?.tier2ChipAi.condition === 'SHARP' ? 'USED' : 'SHARP'} ] สั่ง Retrain ทันที!
                    </span>
                  </div>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-200 text-amber-900 font-bold animate-pulse">
                  Auto Retrain
                </span>
              </button>

              {/* Option C: Discrepancy 2 (Triggers YOLOv8 Retrain) */}
              <button
                disabled={isSubmitting}
                onClick={() => handleHumanSignOff(qcData?.tier2ChipAi.condition === 'DULLED' ? 'USED' : 'DULLED')}
                className="w-full p-2.5 rounded-xl border border-indigo-200 hover:border-indigo-400 bg-indigo-50/50 hover:bg-indigo-100/60 text-left transition flex items-center justify-between group shadow-xs cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-indigo-600 group-hover:scale-110 transition" />
                  <div>
                    <span className="text-xs font-bold text-indigo-950 block">
                      โมเดลบอก {qcData?.tier2ChipAi.condition} แต่มีดจริงเป็น [ {qcData?.tier2ChipAi.condition === 'DULLED' ? 'USED' : 'DULLED'} ]
                    </span>
                    <span className="text-[10px] text-indigo-700 font-mono">
                      ⚡ ดึงภาพ chip/{recordId}.jpg คู่กับคำตอบ [ {qcData?.tier2ChipAi.condition === 'DULLED' ? 'USED' : 'DULLED'} ] สั่ง Retrain ทันที!
                    </span>
                  </div>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-200 text-indigo-900 font-bold animate-pulse">
                  Auto Retrain
                </span>
              </button>
            </div>

            {/* Current Sign-Off Summary Details */}
            {currentVerified && (
              <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 text-[11px] font-mono space-y-1">
                <div className="flex justify-between text-gray-500">
                  <span>Inspector Decision:</span>
                  <span className="font-bold text-gray-900">{currentVerified.status}</span>
                </div>
                <div className="flex justify-between text-gray-500">
                  <span>Sign-Off By:</span>
                  <span>{currentVerified.verifiedBy}</span>
                </div>
                <div className="flex justify-between text-gray-500">
                  <span>Timestamp:</span>
                  <span>{currentVerified.verifiedAt}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      )}
    </div>
  );
}

export default VisualQcPage;
