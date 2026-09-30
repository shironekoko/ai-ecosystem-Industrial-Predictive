import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  BrainCircuit,
  Database,
  CheckCircle2,
  Cpu,
  Sparkles,
  GitBranch,
  ArrowRight,
  TrendingUp,
  AlertCircle,
  ShieldCheck,
  ZapOff,
  Eye,
} from 'lucide-react';
import { PageHeader } from '../../components/common/PageHeader';
import { StatCard } from '../../components/common/StatCard';
import { StatusBadge } from '../../components/common/StatusBadge';
import { EmptyState } from '../../components/common/EmptyState';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { ModelRegistryItem } from '../../types';

export function ActiveLearningPage() {
  const { isAuthenticated, user } = useAuth();
  const isAdmin = user?.role === 'admin';

  // Model Registry state
  const [models, setModels] = useState<ModelRegistryItem[]>([]);
  const [verifiedSamplesCount, setVerifiedSamplesCount] = useState<number>(14);

  useEffect(() => {
    api.getRegisteredModels().then((data) => {
      if (data && data.length > 0) {
        setModels(data);
      }
    });
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Model Registry & Active Learning"
        subtitle="Automated Human-in-the-Loop continuous learning queue · MLflow model registry"
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge
              status={models.length > 0 ? 'connected' : 'disconnected'}
              label={models.length > 0 ? 'MLflow: Connected' : 'MLflow: Standby'}
            />
            <span className="text-xs px-2.5 py-1 rounded-md bg-purple-50 text-purple-700 font-semibold border border-purple-200">
              HITL Active Retraining Loop
            </span>
          </div>
        }
      />

      {/* HITL Policy Banner */}
      <div className="p-4 rounded-xl bg-gradient-to-r from-purple-50 via-indigo-50 to-blue-50 border border-purple-200/80 text-purple-950 text-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-purple-600 text-white rounded-lg shrink-0 mt-0.5 md:mt-0 shadow-sm">
            <GitBranch className="w-4 h-4" />
          </div>
          <div>
            <div className="font-bold text-sm text-purple-900 flex items-center gap-2">
              <span>นโยบาย Automated Human-in-the-Loop Active Retraining Queue</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-200/70 text-purple-800">
                Zero-Manual Button
              </span>
            </div>
            <p className="text-gray-600 mt-0.5 leading-relaxed">
              การ Retrain จะเกิดขึ้นโดย<strong>อัตโนมัติทันที</strong>เมื่อวิศวกรตรวจพบ False Alarm ในหน้า <strong>Tool Verification Bench</strong> (โมเดลบอก DULLED แต่มีดจริงยังเป็น SHARP หรือ USED) โดยไม่มีปุ่มกด Retrain เองเพื่อป้องกันความผิดพลาดและการเทรนซ้ำซ้อน
            </p>
          </div>
        </div>
        <Link
          to="/visual-qc"
          className="inline-flex items-center gap-1.5 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-bold text-xs shrink-0 shadow-sm transition active:scale-95"
        >
          <span>ไปที่ Tool Verification Bench</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          label="Registered Models"
          value={models.length > 0 ? `${models.length} Models` : '2 Models'}
          icon={BrainCircuit}
          accent="purple"
          trend="neutral"
          trendLabel="MLflow tracking"
        />
        <StatCard
          label="Retrain Policy"
          value="HITL Auto-Trigger"
          icon={GitBranch}
          accent="emerald"
          trend="neutral"
          trendLabel="Trigger on Discrepancy"
        />
        <StatCard
          label="Retraining Scope"
          value="YOLOv8 Vision Only"
          icon={Eye}
          accent="blue"
          trend="neutral"
          trendLabel="Keyence Optical Microscope"
        />
        <StatCard
          label="Telemetry Data"
          value="Runtime Stop Only"
          icon={ZapOff}
          accent="amber"
          trend="neutral"
          trendLabel="Not collected for retrain"
        />
      </div>

      {/* Automated HITL Retraining Queue Pipeline Diagram */}
      <div className="p-6 bg-white border border-gray-200 rounded-xl shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-3">
          <div>
            <h4 className="font-bold text-sm text-gray-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-600" />
              <span>สถาปัตยกรรมคิว Retrain อัตโนมัติ (Automated HITL Pipeline)</span>
            </h4>
            <p className="text-xs text-gray-500 mt-0.5">
              การทำงานร่วมกันระหว่าง Machine Monitoring, Human Verification Bench และ MLOps Worker
            </p>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Queue Worker: Online (ARQ + Redis)
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-2">
          {/* Step 1 */}
          <div className="p-4 rounded-xl bg-gray-50 border border-gray-200/80 space-y-2 relative">
            <div className="text-[10px] font-bold font-mono text-gray-400 uppercase tracking-wider">Step 1 · Runtime Trigger</div>
            <h5 className="font-bold text-xs text-gray-900 flex items-center gap-1.5">
              <span>Time-Series หยุดเครื่อง</span>
            </h5>
            <p className="text-[11px] text-gray-600 leading-relaxed">
              เมื่อโมเดล 1D-CNN+BiLSTM วิเคราะห์แรงตัด (Fres) และทำนายได้ <strong>DULL</strong> ระบบจะส่งสัญญาณหยุดเครื่องจักรที่ Run นั้นทันที และส่งใบมีดไปตรวจยืนยัน
            </p>
            <div className="text-[10px] font-mono text-amber-700 bg-amber-50 px-2 py-1 rounded border border-amber-200">
              *ข้อมูลแรงตัดไม่ถูกเก็บมา Retrain
            </div>
          </div>

          {/* Step 2 */}
          <div className="p-4 rounded-xl bg-purple-50/60 border border-purple-200/80 space-y-2 relative">
            <div className="text-[10px] font-bold font-mono text-purple-600 uppercase tracking-wider">Step 2 · Optical Inspection</div>
            <h5 className="font-bold text-xs text-purple-900 flex items-center gap-1.5">
              <span>ตรวจเช็คที่ Verification Bench</span>
            </h5>
            <p className="text-[11px] text-purple-900 leading-relaxed">
              วิศวกรนำหัวมีดส่องกล้อง Keyence ตรวจรอยสึก (Flank Wear Vb, Gaps) ควบคู่กับผลทำนายจาก Vision Model (YOLOv8)
            </p>
            <div className="text-[10px] font-mono text-purple-700 bg-white px-2 py-1 rounded border border-purple-200">
              Target: Tool 10 Flutes #1-#4
            </div>
          </div>

          {/* Step 3 */}
          <div className="p-4 rounded-xl bg-rose-50/60 border border-rose-200/80 space-y-2 relative">
            <div className="text-[10px] font-bold font-mono text-rose-600 uppercase tracking-wider">Step 3 · Human Answer</div>
            <h5 className="font-bold text-xs text-rose-900 flex items-center gap-1.5">
              <span>ระบุคำตอบจริง (Ground Truth)</span>
            </h5>
            <p className="text-[11px] text-rose-900 leading-relaxed">
              หากโมเดลบอก <strong>DULLED</strong> แต่วิศวกรพบว่ามีดจริงเป็น <strong>SHARP</strong> หรือ <strong>USED</strong> ระบบจะดึงภาพจาก <strong>chip/</strong> ของใบมีดนั้นคู่กับ<strong>คำตอบของผู้ใช้</strong>เข้าคิว Retrain ทันที
            </p>
            <div className="text-[10px] font-mono text-rose-700 bg-white px-2 py-1 rounded border border-rose-200 font-bold">
              Input: chip/ + User Answer
            </div>
          </div>

          {/* Step 4 */}
          <div className="p-4 rounded-xl bg-emerald-50/60 border border-emerald-200/80 space-y-2 relative">
            <div className="text-[10px] font-bold font-mono text-emerald-600 uppercase tracking-wider">Step 4 · Model Checkpoint</div>
            <h5 className="font-bold text-xs text-emerald-900 flex items-center gap-1.5">
              <span>Fine-Tune YOLOv8 Vision</span>
            </h5>
            <p className="text-[11px] text-emerald-900 leading-relaxed">
              ARQ Worker นำภาพจาก <strong>chip/</strong> พร้อมคำตอบของผู้ใช้ไปเพิ่มในโฟลเดอร์ <code>train/{'{user_answer}'}/</code> แล้ว Fine-tune <strong>yolov8_chip_wear</strong> บันทึก Checkpoint ลง MLflow
            </p>
            <div className="text-[10px] font-mono text-emerald-700 bg-white px-2 py-1 rounded border border-emerald-200">
              MLflow Model Version Updated
            </div>
          </div>
        </div>
      </div>

      {/* Dual AI Pipelines Definition Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Pipeline 1: Pure Time-Series CRNN */}
        <div className="p-5 bg-white border border-gray-200 rounded-xl shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                <Cpu className="w-5 h-5" />
              </div>
              <div>
                <h4 className="font-bold text-sm text-gray-900">Force Sensor AI Pipeline (Runtime Only)</h4>
                <p className="text-xs text-gray-500">1D-CNN + BiLSTM Multi-Task (Wear Class + Vb Regression)</p>
              </div>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-100 text-gray-600 font-bold">
              Time-Series Modality
            </span>
          </div>
          <p className="text-xs text-gray-600 leading-relaxed">
            รับสัญญาณแรงตัดความถี่สูง (Fx, Fy, Fres) จาก Dynamic Telemetry Stream เพื่อทำนายการสึกหรอและสั่งหยุด Spindle เมื่อถึงสภาวะ DULL ไม่มีการเก็บข้อมูลสตรีมมิ่งมาใช้ Retrain ซ้ำ
          </p>
          <div className="pt-2 border-t border-gray-100 flex items-center justify-between text-xs font-mono text-gray-500">
            <span>Model: model_timeseries/</span>
            <span className="text-amber-600 font-bold">Status: Fixed Weights (No Retrain)</span>
          </div>
        </div>

        {/* Pipeline 2: YOLOv8-cls */}
        <div className="p-5 bg-white border border-gray-200 rounded-xl shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <h4 className="font-bold text-sm text-gray-900">Optical Vision AI Pipeline (Continuous Learning)</h4>
                <p className="text-xs text-gray-500">YOLOv8 Vision Classifier (Keyence Microscope Images)</p>
              </div>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-50 text-purple-700 font-bold border border-purple-200">
              Active Retrain Target
            </span>
          </div>
          <p className="text-xs text-gray-600 leading-relaxed">
            โมเดลวิเคราะห์ภาพถ่ายกล้องจุลทรรศน์สำหรับตรวจสอบรอยสึกบนคมมีดและเศษตัด (Chips) เป็นโมเดลเดียวในระบบที่ทำการ Retrain ผ่าน Human-in-the-Loop เมื่อวิศวกรแย้งผลทำนาย
          </p>
          <div className="pt-2 border-t border-gray-100 flex items-center justify-between text-xs font-mono text-gray-500">
            <span>Model: yolov8_chip_wear</span>
            <span className="text-emerald-600 font-bold">Status: Auto-Retrain on HITL Discrepancy</span>
          </div>
        </div>
      </div>

      {/* Models Directory Table */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
          <div>
            <h3 className="font-bold text-gray-900 text-sm">MLflow Registered Model Checkpoints</h3>
            <p className="text-xs text-gray-500 mt-0.5">Model version history and evaluation metrics</p>
          </div>
          <span className="text-xs font-mono text-gray-400">Total Models: {models.length}</span>
        </div>

        {models.length === 0 ? (
          <div className="py-14">
            <EmptyState
              icon={BrainCircuit}
              title="No Models Registered in MLflow"
              description="Trained model checkpoints and validation F1-scores will appear here once connected to the MLflow model registry API."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-gray-50 text-[11px] uppercase tracking-wider text-gray-400 font-semibold border-b border-gray-100">
                <tr>
                  <th className="px-6 py-3">Model Name</th>
                  <th className="px-4 py-3">Architecture</th>
                  <th className="px-4 py-3">Modality</th>
                  <th className="px-4 py-3">Accuracy</th>
                  <th className="px-4 py-3">F1-Score</th>
                  <th className="px-4 py-3">Retrain Mode</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {models.map((m) => {
                  const isVision = m.modality?.toLowerCase().includes('vision') || m.name?.toLowerCase().includes('yolo');
                  return (
                    <tr key={m.id} className="hover:bg-gray-50/70 transition">
                      <td className="px-6 py-4 font-sans font-bold text-gray-900">{m.name}</td>
                      <td className="px-4 py-4 text-gray-600">{m.architecture}</td>
                      <td className="px-4 py-4 text-gray-500">{m.modality}</td>
                      <td className="px-4 py-4 font-bold text-emerald-600">
                        {typeof m.accuracy === 'number'
                          ? m.accuracy <= 1
                            ? `${(m.accuracy * 100).toFixed(1)}%`
                            : `${m.accuracy}%`
                          : m.accuracy}
                      </td>
                      <td className="px-4 py-4 text-gray-800">{m.f1Score}</td>
                      <td className="px-4 py-4 font-sans">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                            isVision
                              ? 'bg-purple-50 text-purple-700 border-purple-200'
                              : 'bg-gray-50 text-gray-500 border-gray-200'
                          }`}
                        >
                          {isVision ? '⚡ HITL Auto-Queue' : '🔒 Fixed Runtime'}
                        </span>
                      </td>
                      <td className="px-4 py-4 font-sans">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                            m.status === 'PRODUCTION'
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : m.status === 'STAGING'
                              ? 'bg-blue-50 text-blue-700 border-blue-200'
                              : 'bg-gray-100 text-gray-600 border-gray-200'
                          }`}
                        >
                          {m.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default ActiveLearningPage;
