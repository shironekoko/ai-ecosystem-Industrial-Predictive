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

  // Read dispatched tool parameters from URL query params (defaults to Tool 10, Run 12)
  const searchParams = new URLSearchParams(location.search);
  const toolParam = searchParams.get('tool');
  const runParam = searchParams.get('run');
  const toolId = toolParam ? Number(toolParam) : 10;
  const passIndex = runParam ? Number(runParam) : 12;

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
  const flankWear = qcData?.tier3ToolEdge.flankWearUm ?? 135.2;
  const gaps = qcData?.tier3ToolEdge.gapsUm ?? 18.4;
  const overhang = qcData?.tier3ToolEdge.overhangUm ?? 14.1;
  const isBrokenOrWorn = flankWear >= 130.0 || gaps > 15.0; // พังจริง (Vb >= 130 หรือ บิ่นจริง)

  // Automated Physical Verification & Retrain dispatch without manual confirm buttons
  useEffect(() => {
    if (!qcData) return;

    const flankWearVal = qcData.tier3ToolEdge?.flankWearUm ?? 135.2;
    const gapsVal = qcData.tier3ToolEdge?.gapsUm ?? 18.4;
    const isBroken = flankWearVal >= 130.0 || gapsVal > 15.0;
    const currentStatus = verifiedBlades[selectedBlade]?.status;

    const engineerName = user?.name ? `${user.name} (Automated)` : 'Automated Optical Metrology';
    const nowTime = new Date().toLocaleTimeString();

    if (isBroken) {
      // พังจริง -> ผ่านการตรวจ & สั่งเปลี่ยนมีดอัตโนมัติ (ไม่ต้องกดยืนยัน)
      if (currentStatus !== 'CONFIRMED_WEAR') {
        setVerifiedBlades((prev) => ({
          ...prev,
          [selectedBlade]: {
            status: 'CONFIRMED_WEAR',
            verifiedBy: engineerName,
            verifiedAt: nowTime,
            message: 'มีดพังจริง (ผ่านเกณฑ์การตรวจ Vb >= 130 µm): สั่งเปลี่ยนมีดอัตโนมัติ',
          },
        }));
        api.submitVerification(
          recordId,
          toolId,
          passIndex,
          selectedBlade,
          'CONFIRMED_WEAR',
          `Automated physical inspection confirmed wear (Vb = ${flankWearVal} µm). Tool replacement approved.`,
          engineerName
        );
      }
    } else {
      // ไม่พังจริง -> ส่งเข้า Retrain Pool อัตโนมัติทันที โดยไม่ต้องมีปุ่มยืนยัน
      if (currentStatus !== 'RETRAIN_FLAGGED') {
        setVerifiedBlades((prev) => ({
          ...prev,
          [selectedBlade]: {
            status: 'RETRAIN_FLAGGED',
            verifiedBy: engineerName,
            verifiedAt: nowTime,
            message: 'มีดยังไม่พัง (False Alarm): ส่งภาพ Chip เข้า Retrain Pool อัตโนมัติ',
          },
        }));
        api.submitVerification(
          recordId,
          toolId,
          passIndex,
          selectedBlade,
          'SEND_TO_RETRAIN',
          `Automated physical inspection detected intact edge (Vb = ${flankWearVal} µm). Chip image dispatched to Retrain Pool.`,
          engineerName
        );
        showToast(`📦 ส่ง Retrain อัตโนมัติ: Blade #${selectedBlade} มีดยังไม่พัง ส่งภาพ Chip เข้า Retrain Pool เรียบร้อย`);
      }
    }
  }, [qcData, selectedBlade, recordId, toolId, passIndex, user?.name]);

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

      {/* Two-Factor Alert Context Banner from In-Process Monitoring */}
      <div className="p-4 bg-gradient-to-r from-slate-900 to-indigo-950 text-white rounded-xl shadow-sm border border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-indigo-500/20 border border-indigo-400/30 text-indigo-300">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-rose-500/20 border border-rose-500/40 text-rose-300 font-bold">
                In-Process 2-Factor Alert Triggered
              </span>
              <span className="text-xs text-slate-300 font-mono">
                Tool #{toolId} · Machining Pass #{passIndex}
              </span>
            </div>
            <p className="text-xs text-slate-200 mt-1">
              หัวมีดถูกถอดออกมาตรวจสอบที่แท่นส่องกล้อง หลังจากระบบ 2-Factor ที่หน้า Telemetry (Time-Series Force AI + Non-Time Chip Model) แจ้งเตือนความสึกหรอ
            </p>
          </div>
        </div>

        <div className="text-right font-mono text-xs text-slate-400">
          <span>Station: </span>
          <strong className="text-white">Bench #1 (Keyence VHX Optical Fixture)</strong>
        </div>
      </div>

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

        {/* 4-Flute Blade Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
            Select Flute/Blade:
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

      {/* Main Grid: Microscope Viewport + Image Processing Vb Metrology & Consensus Sign-Off */}
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

        {/* Right Column: Image Processing Ground Truth Metrology & Sign-Off Hub */}
        <div className="col-span-12 lg:col-span-5 space-y-5">
          {/* Card 1: Image Processing Edge Metrology (หาค่า Vb และรอยบิ่นจริง) */}
          <div className="p-5 bg-white border border-gray-200 rounded-xl shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <span className="font-bold text-xs uppercase tracking-wider text-purple-700 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-purple-600" />
                <span>Image Processing Ground Truth (หาค่า Vb)</span>
              </span>
              <span className="text-[10px] font-mono bg-purple-50 text-purple-700 border border-purple-200 px-2 py-0.5 rounded font-bold">
                ISO 8688 Metrology
              </span>
            </div>

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
                  {gaps} µm {gaps > 15 ? '(บิ่นจริง)' : '(ขอบเรียบ)'}
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

          {/* Card 2: Physical Verification Decision (เช็คว่าพังจริงไหม & ดำเนินการอัตโนมัติ) */}
          <div className="p-5 bg-white border border-gray-200 rounded-xl shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-xs uppercase tracking-wider text-gray-800 flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-indigo-600" />
                <span>Physical Verification (เช็คว่าพังจริงไหม)</span>
              </h4>
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                  isBrokenOrWorn
                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                    : 'bg-amber-100 text-amber-800 border border-amber-200'
                }`}
              >
                {isBrokenOrWorn ? 'VERIFICATION PASSED' : 'AUTO-SENT TO RETRAIN'}
              </span>
            </div>

            {/* Verdict Explanation Box */}
            <div
              className={`p-4 rounded-xl border text-xs space-y-2 ${
                isBrokenOrWorn
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-950'
                  : 'bg-amber-50 border-amber-200 text-amber-950'
              }`}
            >
              <div className="flex items-center gap-2 font-bold text-xs">
                {isBrokenOrWorn ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                ) : (
                  <Database className="w-4 h-4 text-amber-600 shrink-0" />
                )}
                <span>
                  {isBrokenOrWorn
                    ? 'ผลการวัดยืนยัน: มีดพังจริง (ผ่านเกณฑ์การตรวจสอบ & สั่งเปลี่ยนมีดอัตโนมัติ)'
                    : 'ผลการวัด: มีดยังไม่พัง (ส่งภาพ Chip เข้า Retrain Pool อัตโนมัติ)'}
                </span>
              </div>
              <p className="text-[11px] text-gray-600 leading-relaxed">
                {isBrokenOrWorn
                  ? `ค่ารอยสึก Vb = ${flankWear} µm เกินเกณฑ์มาตรฐาน ISO (130 µm) และพบรอยบิ่น ${gaps} µm ยืนยันว่าโมเดลทำนายถูกต้อง ถือว่าผ่านการตรวจ ระบบอนุมัติคำสั่งเปลี่ยนหัวมีดตัดใหม่เรียบร้อย (ไม่ต้องกดยืนยันซ้ำซ้อน)`
                  : `ค่ารอยสึก Vb = ${flankWear} µm และขอบมีดยังเรียบเนียน ไม่พบรอยบิ่น แสดงว่าโมเดล Non-Time-Series ทำนายคลาดเคลื่อน (False Alarm) ระบบได้ส่งภาพ Chip ในรอบตัดนี้เข้า Retrain Pool อัตโนมัติทันที`}
              </p>
            </div>

            {/* Automated Execution Status Details */}
            <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-100 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-gray-500 font-medium">สถานะการทำงาน:</span>
                <span
                  className={`font-bold font-mono px-2 py-0.5 rounded text-[10px] ${
                    isBrokenOrWorn
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-amber-100 text-amber-800'
                  }`}
                >
                  {isBrokenOrWorn ? 'APPROVED: TOOL REPLACEMENT' : 'DISPATCHED: RETRAIN POOL'}
                </span>
              </div>
              <div className="flex items-center justify-between text-gray-500 text-[11px] font-mono">
                <span>Target Flute:</span>
                <span className="font-bold text-gray-800">{recordId}</span>
              </div>
              <div className="flex items-center justify-between text-gray-500 text-[11px] font-mono">
                <span>Active Learning Pool:</span>
                <span className="font-bold text-indigo-600">
                  {isBrokenOrWorn ? 'Ground Truth Confirmed' : 'Retrain Queue (Active)'}
                </span>
              </div>
              {currentVerified && (
                <div className="flex items-center justify-between text-gray-400 text-[10px] font-mono pt-1 border-t border-gray-200/60">
                  <span>Logged At:</span>
                  <span>{currentVerified.verifiedAt}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default VisualQcPage;
