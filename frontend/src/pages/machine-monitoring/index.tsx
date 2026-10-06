import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { AlertOctagon, FileText, PackageCheck, Pause, Play, RotateCcw, ScanEye, Wrench } from 'lucide-react';
import { PageHeader } from '../../components/common';
import {
  Card,
  ConnBadge,
  MACHINE_COLOR,
  PHASE_TEXT,
  RecBadge,
  STATE_STYLE,
  StreamBadge,
  WearBadge,
  fmt,
  fmtClock,
  fmtDateTime,
} from '../../components/toollife/ui';
import { useFleet, useMachineHistory, useWaveform } from '../../hooks/useToolLife';
import { api } from '../../services/api';
import type { MachineSnapshot, RunRecord, VisionInspection } from '../../types';

const LAYER_MIN = 164 / 60;

const SIGNALS = {
  forces: { label: 'แรงตัด (dynamometer)', unit: 'N', keys: [['fx', 'Fx', '#6366f1'], ['fy', 'Fy', '#0ea5e9'], ['fz', 'Fz', '#14b8a6']] },
  spindle: { label: 'แรงบิด spindle', unit: 'Nm', keys: [['sp', 'Spindle torque', '#f59e0b']] },
  axis: { label: 'มอเตอร์แกนป้อน X/Y', unit: '', keys: [['ax', 'Axis X', '#8b5cf6'], ['ay', 'Axis Y', '#ec4899']] },
} as const;

const REL_KEYS: [string, string, string][] = [
  ['sp_rel', 'แรงบิด spindle', '#f59e0b'],
  ['ay_rel', 'มอเตอร์แกน Y', '#ec4899'],
  ['ax_rel', 'มอเตอร์แกน X', '#8b5cf6'],
  ['fres_rel', 'แรงลัพธ์ Fres', '#6366f1'],
  ['fx_rel', 'แรง Fx', '#0ea5e9'],
];

/** ติดตั้งดอกใหม่ตามใบเบิกแล้ว แต่ยังไม่เริ่มตัด */
const freshTool = (m: MachineSnapshot) => !!m.installed && !m.started_at;

const Controls: React.FC<{ m: MachineSnapshot; speeds: number[] }> = ({ m, speeds }) => {
  const [busy, setBusy] = useState(false);
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
    } catch (e: any) {
      alert(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      {m.state === 'IDLE' ? (
        <button disabled={busy} onClick={() => run(() => api.controlMachine(m.machine, 'start'))} className="btn-primary">
          <Play className="w-3.5 h-3.5" /> เริ่มตัด
        </button>
      ) : m.state === 'PAUSED' ? (
        <button disabled={busy} onClick={() => run(() => api.controlMachine(m.machine, 'resume'))} className="btn-primary">
          <Play className="w-3.5 h-3.5" /> {freshTool(m) ? 'เริ่มตัด (ดอกใหม่)' : 'ตัดต่อ'}
        </button>
      ) : m.state === 'CUTTING' ? (
        <button disabled={busy} onClick={() => run(() => api.controlMachine(m.machine, 'pause'))} className="btn-secondary">
          <Pause className="w-3.5 h-3.5" /> หยุดชั่วคราว
        </button>
      ) : null}
      <button
        disabled={busy}
        onClick={() => confirm('รีเซ็ตสตรีมและเริ่มดอกนี้ใหม่จากรันแรก?') && run(() => api.controlMachine(m.machine, 'reset'))}
        className="btn-secondary"
      >
        <RotateCcw className="w-3.5 h-3.5" /> รีเซ็ต
      </button>
      <label className="flex items-center gap-1.5 text-xs text-gray-600 ml-1">
        ความเร็วเล่นซ้ำ
        <select
          value={m.speed}
          onChange={(e) => run(() => api.setSpeed(m.machine, Number(e.target.value)))}
          className="border border-gray-200 rounded-md px-2 py-1 text-xs bg-white"
        >
          {speeds.map((s) => (
            <option key={s} value={s}>
              {s === 1 ? '1× (เวลาจริง)' : `${s}× (เร่งเวลา)`}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
};

const HoldBanner: React.FC<{ m: MachineSnapshot }> = ({ m }) => {
  const navigate = useNavigate();
  const p = m.prediction;
  const [busy, setBusy] = useState(false);
  const remove = async () => {
    setBusy(true);
    try {
      const snap = await api.acknowledge(m.machine, 'replace');
      // ถอดดอกแล้ว → ระบบถ่ายภาพใบมีด 4 ใบ + AI วิเคราะห์ → ไปยืนยันผลต่อที่ Tool Inspection
      navigate(snap.inspection ? `/tool-vision?tab=review&inspection=${snap.inspection.id}` : '/tool-vision');
    } catch (e: any) {
      alert(e.message || String(e));
      setBusy(false);
    }
  };
  return (
    <div className="p-4 rounded-xl border-2 border-red-300 bg-red-50 flex flex-col md:flex-row md:items-center gap-4">
      <AlertOctagon className="w-8 h-8 text-red-600 shrink-0" />
      <div className="flex-1">
        <p className="font-bold text-red-800">Interlock: ดอก {m.tool_id} บน {m.machine_id} หมดอายุ — ระบบแนะนำให้เปลี่ยนดอก</p>
        <p className="text-sm text-red-700">
          RUL ≈ {fmt(p?.rul_min)} นาที (P10 {fmt(p?.rul_lo)}) — เครื่องหยุดป้อน (feed hold) รอการตัดสินใจของผู้ควบคุม · ถอดดอกแล้วระบบจะถ่ายภาพใบมีด 4 ใบให้ AI
          ตรวจต่อที่ Tool Inspection · การตัดสินใจทุกครั้งถูกบันทึกใน Audit Trail
        </p>
      </div>
      <div className="flex gap-2">
        <button disabled={busy} onClick={remove} className="btn-danger">
          <Wrench className={`w-3.5 h-3.5 ${busy ? 'animate-spin' : ''}`} /> {busy ? 'กำลังถอดดอกและถ่ายภาพใบมีด…' : 'ถอดดอก → ตรวจใบมีด'}
        </button>
        <button disabled={busy} onClick={() => api.acknowledge(m.machine, 'continue')} className="btn-secondary">
          ตัดต่อ (override)
        </button>
      </div>
    </div>
  );
};

/** ดอกที่เพิ่งถอด: ตรวจใบมีด → ใบเบิกดอกทดแทน → รับจากคลัง → ติดตั้ง (ขั้นต่อไปอยู่ที่ Tool Inspection) */
const RemovedBanner: React.FC<{ m: MachineSnapshot }> = ({ m }) => {
  const [ins, setIns] = useState<VisionInspection | null>(null);
  const id = m.inspection?.id;
  useEffect(() => {
    if (!id) {
      setIns(null);
      return;
    }
    const load = () => api.getInspection(id).then(setIns).catch(() => {});
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [id]);
  const req = ins?.requisition;
  const fs = ins?.final_summary;
  return (
    <div className="p-3 rounded-lg bg-indigo-50 border border-indigo-200 text-sm text-indigo-800 flex flex-col md:flex-row md:items-center gap-3">
      <div className="flex-1 space-y-0.5">
        <p>
          ดอก {m.tool_id} ถูกถอดแล้ว ({m.completed?.reason === 'REPLACED_BY_OPERATOR' ? `ผู้ควบคุม${m.completed?.by ? ` ${m.completed.by}` : ''} ถอดดอก` : 'สิ้นสุดข้อมูลการทดลอง'} ที่เวลาตัด{' '}
          {fmt(m.completed?.t_min)} นาที) — เครื่องรอดอกใหม่ · ผลเทียบกับ VB ที่วัดจริงอยู่ในหน้า Reports
        </p>
        <p className="text-xs flex items-center gap-1.5">
          <ScanEye className="w-3.5 h-3.5" />
          {!m.inspection
            ? 'กำลังถ่ายภาพใบมีด 4 ใบให้ AI วัดรอยสึก VB…'
            : !ins || ins.status === 'PENDING_REVIEW'
            ? `ตรวจใบมีด ${m.inspection.id}: AI วัด VB เฉลี่ย 4 ใบ ${ins?.ai_summary ? `${ins.ai_summary.mean_vb.toFixed(0)} µm` : '—'} — รอผู้ตรวจยืนยันที่ Tool Inspection`
            : req?.status === 'ISSUED'
            ? `ใบเบิก ${req.req_no}: รับดอกจากคลังแล้ว (${req.issued_by}) — ติดตั้งบนเครื่องแล้วกด "ติดตั้งดอกใหม่แล้ว"`
            : `ตรวจแล้ว: VB เฉลี่ย ${fs ? `${fs.mean_vb.toFixed(0)} µm` : '—'} → ออกใบเบิก ${req?.req_no ?? ''} — รอเบิกดอกจากคลังเครื่องมือ`}
        </p>
      </div>
      <Link
        to={ins?.status === 'VERIFIED' ? '/tool-vision?tab=requisition' : m.inspection ? `/tool-vision?tab=review&inspection=${m.inspection.id}` : '/tool-vision'}
        className="btn-primary shrink-0"
      >
        {ins?.status === 'VERIFIED' ? <FileText className="w-3.5 h-3.5" /> : <ScanEye className="w-3.5 h-3.5" />}{' '}
        {ins?.status === 'VERIFIED' ? 'ใบเบิกดอก' : 'ไปที่ Tool Inspection'}
      </Link>
    </div>
  );
};

/** ติดตั้งดอกใหม่ตามใบเบิกแล้ว — เครื่องหยุดชั่วคราวจนกว่าผู้ควบคุมกดเริ่มตัด */
const InstalledBanner: React.FC<{ m: MachineSnapshot }> = ({ m }) => (
  <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-sm text-emerald-800 flex items-center gap-3">
    <PackageCheck className="w-5 h-5 shrink-0" />
    <p className="flex-1">
      ติดตั้งดอกใหม่ {m.tool_id} บน {m.machine_id} แล้วตามใบเบิก <b>{m.installed?.req_no}</b> (โดย {m.installed?.by} · {fmtDateTime(m.installed?.at)}) — เครื่องหยุดชั่วคราว
      กด <b>เริ่มตัด (ดอกใหม่)</b> เมื่อพร้อม
    </p>
  </div>
);

const WaveformPanel: React.FC<{ machine: number; m: MachineSnapshot }> = ({ machine, m }) => {
  const { points, run } = useWaveform(machine);
  const [sig, setSig] = useState<keyof typeof SIGNALS>('forces');
  const cfg = SIGNALS[sig];
  const unit = sig === 'axis' ? (m.machine === 1 ? 'Nm' : 'N') : cfg.unit;
  return (
    <Card
      title={`สัญญาณสด — รัน ${run ?? '—'}`}
      right={
        <div className="flex gap-1">
          {(Object.keys(SIGNALS) as (keyof typeof SIGNALS)[]).map((k) => (
            <button
              key={k}
              onClick={() => setSig(k)}
              className={`px-2 py-1 rounded-md text-[11px] font-medium ${sig === k ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              {SIGNALS[k].label}
            </button>
          ))}
        </div>
      }
    >
      <div className="h-56">
        {points.length === 0 ? (
          <div className="h-full flex items-center justify-center text-sm text-gray-400 text-center px-6">
            {m.state === 'CUTTING' && m.current && !m.current.recorded
              ? 'เครื่องกำลังตัดแนวที่ไม่ได้ถูกบันทึกในชุดข้อมูล — สัญญาณจะกลับมาเมื่อถึงรันถัดไป'
              : m.state === 'CUTTING'
              ? 'กำลังรับสัญญาณ…'
              : 'ไม่มีการตัดในขณะนี้'}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#f1f5f9" />
              <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(v) => `${v.toFixed(1)}s`} tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} width={48} unit={unit ? ` ${unit}` : ''} />
              <Tooltip formatter={(v: number) => v.toFixed(2)} labelFormatter={(l) => `t = ${Number(l).toFixed(3)} s`} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {cfg.keys.map(([k, label, color]) => (
                <Line key={k} dataKey={k} name={label} stroke={color} dot={false} strokeWidth={1.3} isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      <p className="text-[11px] text-gray-400 mt-2">
        ข้อมูลจริงจากไฟล์ h5 ของรันนี้ เล่นที่อัตรา controller 500 Hz (แรง dynamometer 25 kHz เฉลี่ยเป็นบล็อก) · หน้าต่าง 3 วินาทีล่าสุด
      </p>
    </Card>
  );
};

const RulChart: React.FC<{ history: RunRecord[]; color: string }> = ({ history, color }) => {
  const data = useMemo(
    () =>
      history
        .filter((h) => h.rul !== null && h.rul !== undefined)
        .map((h) => ({ t: h.t_min, rul: h.rul, band: [h.rul_lo, h.rul_hi], raw: h.raw_rul })),
    [history],
  );
  if (data.length === 0)
    return <div className="h-72 flex items-center justify-center text-sm text-gray-400">ยังไม่มีผลพยากรณ์ (ต้องผ่าน break-in + เก็บค่าตั้งต้น 29 รันก่อน)</div>;
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 5, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#f1f5f9" />
          <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tick={{ fontSize: 10 }} tickFormatter={(v) => `${v.toFixed(0)}`} label={{ value: 'เวลาตัดสะสม (นาที)', position: 'insideBottom', offset: -2, fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} width={40} domain={[0, 'auto']} label={{ value: 'RUL (นาที)', angle: -90, position: 'insideLeft', fontSize: 10 }} />
          <Tooltip
            formatter={(v: any, n: string) => (Array.isArray(v) ? `${v[0].toFixed(1)}–${v[1].toFixed(1)}` : Number(v).toFixed(2)) + ' นาที'}
            labelFormatter={(l) => `เวลาตัด ${Number(l).toFixed(2)} นาที`}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Area dataKey="band" name="ช่วง P10–P90" stroke="none" fill={color} fillOpacity={0.15} isAnimationActive={false} />
          <Scatter dataKey="raw" name="ค่าประมาณดิบรายรัน (GRU)" fill="#94a3b8" shape={(p: any) => <circle cx={p.cx} cy={p.cy} r={1.4} fill="#94a3b8" />} isAnimationActive={false} />
          <Line dataKey="rul" name="RUL (หลังข้อจำกัดฟิสิกส์)" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
          <ReferenceLine y={LAYER_MIN} stroke="#ef4444" strokeDasharray="4 3" label={{ value: 'เปลี่ยนทันที (1 ชั้น)', fontSize: 9, fill: '#ef4444', position: 'insideTopRight' }} />
          <ReferenceLine y={3 * LAYER_MIN} stroke="#f97316" strokeDasharray="4 3" label={{ value: 'วางแผน (3 ชั้น)', fontSize: 9, fill: '#f97316', position: 'insideTopRight' }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};

const SensorTrend: React.FC<{ history: RunRecord[] }> = ({ history }) => {
  const data = useMemo(
    () =>
      history
        .filter((h) => h.rel)
        .map((h) => ({ t: h.t_min, ...Object.fromEntries(REL_KEYS.map(([k]) => [k, +(100 * (h.rel as any)[k]).toFixed(2)])) })),
    [history],
  );
  if (data.length === 0) return <div className="h-56 flex items-center justify-center text-sm text-gray-400">รอค่าตั้งต้นของดอก</div>;
  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#f1f5f9" />
          <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tick={{ fontSize: 10 }} tickFormatter={(v) => v.toFixed(0)} />
          <YAxis tick={{ fontSize: 10 }} width={40} unit="%" />
          <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} labelFormatter={(l) => `เวลาตัด ${Number(l).toFixed(2)} นาที`} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {REL_KEYS.map(([k, label, color]) => (
            <Line key={k} dataKey={k} name={label} stroke={color} dot={false} strokeWidth={1.2} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

const StateStrip: React.FC<{ history: RunRecord[] }> = ({ history }) => {
  const pts = history.filter((h) => h.state);
  if (pts.length < 2) return null;
  const t0 = history[0]?.t_min ?? 0;
  const t1 = history[history.length - 1].t_min;
  const span = Math.max(t1 - t0, 1e-6);
  return (
    <div>
      <div className="relative h-4 rounded bg-gray-100 overflow-hidden">
        {pts.map((h, i) => {
          const next = pts[i + 1]?.t_min ?? t1;
          return (
            <div
              key={i}
              className="absolute inset-y-0"
              style={{ left: `${((h.t_min - t0) / span) * 100}%`, width: `${((next - h.t_min) / span) * 100 + 0.2}%`, background: STATE_STYLE[h.state!].color }}
            />
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] text-gray-400 mt-1">
        <span>{t0.toFixed(1)} นาที</span>
        <span className="flex gap-3">
          {Object.entries(STATE_STYLE).map(([k, v]) => (
            <span key={k} className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-sm" style={{ background: v.color }} />
              {v.th}
            </span>
          ))}
        </span>
        <span>{t1.toFixed(1)} นาที</span>
      </div>
    </div>
  );
};

export const MachineMonitoringPage: React.FC = () => {
  const [params, setParams] = useSearchParams();
  const machine = Number(params.get('machine') || 1);
  const { fleet, conn } = useFleet();
  const { history } = useMachineHistory(machine);
  const m = fleet?.machines.find((x) => x.machine === machine);
  const last = history[history.length - 1];
  const p = m?.prediction;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Machine Monitoring"
        subtitle="ติดตามดอกกัดทีละรัน: สัญญาณจริง → ฟีเจอร์รายรัน → แบบจำลองอนุกรมเวลา → RUL / สถานะการสึก / คำแนะนำ"
        actions={<ConnBadge conn={conn} />}
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1 p-1 bg-gray-100 rounded-lg">
          {(fleet?.machines ?? []).map((x) => (
            <button
              key={x.machine}
              onClick={() => setParams({ machine: String(x.machine) })}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 ${
                x.machine === machine ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              <span className="w-2 h-2 rounded-sm" style={{ background: MACHINE_COLOR[x.machine] }} />
              {x.machine_id} · {x.tool_id}
              {x.prediction?.recommendation === 'REPLACE_NOW' && <span className="w-1.5 h-1.5 rounded-full bg-red-500" />}
            </button>
          ))}
        </div>
        {m && fleet && <Controls m={m} speeds={fleet.speeds} />}
      </div>

      {!m ? (
        <div className="text-center text-sm text-gray-400 py-16">กำลังโหลด…</div>
      ) : (
        <>
          {m.state === 'HOLD' && <HoldBanner m={m} />}
          {m.state === 'COMPLETED' && <RemovedBanner m={m} />}
          {m.state === 'PAUSED' && freshTool(m) && <InstalledBanner m={m} />}

          <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
            <div className="col-span-2 p-4 bg-white rounded-xl border border-gray-200 shadow-sm">
              <p className="text-[11px] text-gray-500">อายุใช้งานที่เหลือ (RUL)</p>
              {p ? (
                <>
                  <p className="text-3xl font-bold tabular-nums">
                    {fmt(p.rul_min)} <span className="text-sm font-medium text-gray-400">นาทีของเวลาตัด</span>
                  </p>
                  <p className="text-xs text-gray-500 tabular-nums">
                    P10–P90 {fmt(p.rul_lo)}–{fmt(p.rul_hi)} นาที · ครบอายุราว {fmtClock(p.eta_utc)}
                  </p>
                </>
              ) : (
                <p className="text-sm text-gray-500 mt-2">{m.model_ready ? PHASE_TEXT[m.phase] : 'แบบจำลองยังไม่พร้อม'}</p>
              )}
            </div>
            <div className="p-4 bg-white rounded-xl border border-gray-200 shadow-sm">
              <p className="text-[11px] text-gray-500">คำแนะนำ</p>
              <div className="mt-2">{p ? <RecBadge rec={p.recommendation} size="md" /> : '—'}</div>
            </div>
            <div className="p-4 bg-white rounded-xl border border-gray-200 shadow-sm">
              <p className="text-[11px] text-gray-500">สถานะการสึก</p>
              <div className="mt-2">{p ? <WearBadge state={p.wear_state} /> : '—'}</div>
              {p && <p className="text-[10px] text-gray-400 mt-1">สึกเร่งอีก {fmt(p.rul_accel_min)} นาที</p>}
            </div>
            <div className="p-4 bg-white rounded-xl border border-gray-200 shadow-sm">
              <p className="text-[11px] text-gray-500">เวลาตัดสะสม</p>
              <p className="text-xl font-bold tabular-nums">{fmt(m.t_min)}</p>
              <p className="text-[10px] text-gray-400">นาที</p>
            </div>
            <div className="p-4 bg-white rounded-xl border border-gray-200 shadow-sm">
              <p className="text-[11px] text-gray-500">สตรีม</p>
              <div className="mt-1.5">
                <StreamBadge state={m.state} speed={m.speed} />
              </div>
              <p className="text-[10px] text-gray-400 mt-1 tabular-nums">
                รันที่ {m.run_index}
                {m.current && !m.current.recorded ? ' · ตัดแนวที่ไม่บันทึก' : ''}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <WaveformPanel machine={machine} m={m} />
            <Card title="RUL ตามเวลาตัด (ผลพยากรณ์ระหว่างใช้งาน — ไม่แสดงค่าจริง)">
              <RulChart history={history} color={MACHINE_COLOR[machine]} />
              <div className="mt-3">
                <StateStrip history={history} />
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <div className="xl:col-span-2">
              <Card title="health indicator: การเปลี่ยนแปลงของค่าเฉลี่ยรายรันเทียบค่าตั้งต้นของดอก (%)">
                <SensorTrend history={history} />
                <p className="text-[11px] text-gray-400 mt-2">
                  ค่ารายรันมีรูปแบบฤดูกาลคาบ 29 รัน (ตำแหน่งแนวตัดบนชิ้นงาน) — แบบจำลองจึงรับหน้าต่าง 29 รันล่าสุด (= 1 ชั้นงาน) เป็นอินพุต
                </p>
              </Card>
            </div>
            <Card title={`รันล่าสุด${last ? ` (#${last.run})` : ''}`}>
              {!last ? (
                <p className="text-sm text-gray-400">ยังไม่มีรันที่จบ</p>
              ) : (
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-500">ตำแหน่งแนวตัด x</span>
                    <span className="font-mono">{last.x_pos} mm</span>
                  </div>
                  {Object.entries(last.raw).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-gray-500">{k}</span>
                      <span className="font-mono">{v.toFixed(3)}</span>
                    </div>
                  ))}
                  <div className="flex justify-between pt-2 border-t border-gray-100">
                    <span className="text-gray-500">drift |z|max เทียบข้อมูลฝึก</span>
                    <span className={`font-mono ${last.input_z_max && last.input_z_max > 4 ? 'text-red-600 font-bold' : ''}`}>{fmt(last.input_z_max, 2)}</span>
                  </div>
                  {last.flagged.length > 0 && <p className="text-amber-700">ค่าผิดปกติชั่วขณะ: {last.flagged.join(', ')} (แทนด้วยค่าคาดหมาย)</p>}
                  {last.blocked && <p className="text-red-600">{last.blocked}</p>}
                  <p className="text-gray-400 pt-1">ตัวแปรแกนป้อน: {last.axis_kind === 'torque' ? 'แรงบิดมอเตอร์ (Nm)' : 'แรงมอเตอร์ (N)'}</p>
                </div>
              )}
            </Card>
          </div>

          <Card title="เหตุการณ์ของเครื่องนี้">
            {m.events.length === 0 ? (
              <p className="text-sm text-gray-400">—</p>
            ) : (
              <ul className="space-y-1.5 text-xs">
                {[...m.events].reverse().map((e, i) => (
                  <li key={i} className="flex gap-3">
                    <span className="text-gray-400 tabular-nums w-16 shrink-0">{fmtClock(e.at)}</span>
                    <span className={e.level === 'CRITICAL' ? 'text-red-700 font-medium' : e.level === 'WARNING' ? 'text-amber-700' : 'text-gray-700'}>{e.message}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  );
};

export default MachineMonitoringPage;
