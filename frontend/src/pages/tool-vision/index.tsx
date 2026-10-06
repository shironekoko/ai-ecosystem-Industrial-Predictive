/**
 * Tool Inspection (Vision) — ขั้นต่อจาก Machine Monitoring
 * RUL แจ้งดอกหมดอายุ → ผู้ควบคุมถอดดอก → ถ่ายภาพ 4 ใบมีด (optical bench) → AI วัดรอยสึก VB (µm) ของแต่ละใบ
 * → ระดับดอก = VB เฉลี่ย 4 ใบ เทียบเกณฑ์ 103 / 140 µm (นิยามเดียวกับ RUL) · VB รายใบบอกคมที่สึกมากสุด
 * → ผู้ตรวจยอมรับค่า AI หรือวัดจริง → ใบสั่งงานระดับดอกให้วิศวกร
 * ค่าที่วัดจริงเข้า pool → retrain → promote
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Camera, CheckCircle2, ClipboardCheck, Cpu, Download, Gauge, Microscope, RefreshCw, Ruler, ScanEye, ShieldAlert, Wrench } from 'lucide-react';
import { AuthImage, PageHeader } from '../../components/common';
import { TrainingCurves } from '../../components/toollife/TrainingCurves';
import { Card, RecBadge, StreamBadge, WearBadge, fmt, fmtDateTime } from '../../components/toollife/ui';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { VERSION_STATUS } from '../model-registry/VisionRegistry';
import type {
  BenchMeasurement,
  Replacements,
  RulContext,
  ToolVerdict,
  TrainingJob,
  TrainingPool,
  VbSource,
  VbZone,
  VisionBlade,
  VisionInspection,
  VisionModelInfo,
  VisionStation,
  VisionStats,
  VisionVersion,
  WorkOrder,
} from '../../types';

const VB_ACCEL = 103;
const VB_EOL = 140;
const GAUGE_MAX = 260;
const ZONES: VbZone[] = ['normal', 'accel', 'eol'];
const zoneOf = (vb: number): VbZone => (vb >= VB_EOL ? 'eol' : vb >= VB_ACCEL ? 'accel' : 'normal');
const ZONE_STYLE: Record<VbZone, { th: string; range: string; cls: string; bar: string; solid: string; action: string }> = {
  normal: { th: 'ปกติ', range: `< ${VB_ACCEL} µm`, cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', bar: 'bg-emerald-500', solid: 'bg-emerald-600 text-white', action: 'ใช้ต่อได้' },
  accel: { th: 'ใกล้หมดอายุ', range: `${VB_ACCEL}–${VB_EOL} µm`, cls: 'bg-amber-50 text-amber-700 border-amber-200', bar: 'bg-amber-500', solid: 'bg-amber-500 text-white', action: 'ควรเปลี่ยน' },
  eol: { th: 'หมดอายุ', range: `≥ ${VB_EOL} µm`, cls: 'bg-red-50 text-red-700 border-red-200', bar: 'bg-red-500', solid: 'bg-red-600 text-white', action: 'ต้องเปลี่ยน' },
};
const VERDICT_STYLE: Record<ToolVerdict, { th: string; cls: string }> = {
  OK: { th: 'ใช้งานต่อได้', cls: 'bg-emerald-600 text-white' },
  MONITOR: { th: 'ใกล้หมดอายุ', cls: 'bg-amber-500 text-white' },
  REPLACE: { th: 'ต้องเปลี่ยน/ลับดอก', cls: 'bg-red-600 text-white' },
};
const SOURCE_TEXT: Record<VbSource, string> = { AI: 'ค่า AI', BENCH: 'วัดบน optical bench', MANUAL: 'วัดเอง (กรอก)' };
type Tab = 'stations' | 'review' | 'replace' | 'model';

const ZoneChip: React.FC<{ zone: VbZone | null | undefined; withRange?: boolean }> = ({ zone, withRange }) =>
  zone && ZONE_STYLE[zone] ? (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-semibold border ${ZONE_STYLE[zone].cls}`}>
      {ZONE_STYLE[zone].th}
      {withRange && <span className="ml-1 font-normal opacity-80">({ZONE_STYLE[zone].range})</span>}
    </span>
  ) : (
    <span className="text-gray-300">—</span>
  );

const VerdictChip: React.FC<{ v: ToolVerdict | null | undefined }> = ({ v }) =>
  v ? <span className={`inline-flex px-2 py-0.5 rounded-md text-[11px] font-bold ${VERDICT_STYLE[v].cls}`}>{VERDICT_STYLE[v].th}</span> : null;

/** แถบ VB 0–260 µm: พื้นหลังตามโซน, ช่วง P10–P90 ของ AI, หมุดค่า AI และค่าที่วัดจริง */
const VbGauge: React.FC<{ vb: number | null; lo?: number | null; hi?: number | null; measured?: number | null }> = ({ vb, lo, hi, measured }) => {
  const x = (v: number) => `${(Math.min(Math.max(v, 0), GAUGE_MAX) / GAUGE_MAX) * 100}%`;
  return (
    <div className="space-y-0.5">
      <div className="relative h-3 rounded overflow-hidden flex">
        <div className="h-full bg-emerald-100" style={{ width: x(VB_ACCEL) }} />
        <div className="h-full bg-amber-100" style={{ width: `${((VB_EOL - VB_ACCEL) / GAUGE_MAX) * 100}%` }} />
        <div className="h-full bg-red-100 flex-1" />
        {lo != null && hi != null && <div className="absolute top-0 h-full bg-indigo-400/30" style={{ left: x(lo), width: `calc(${x(hi)} - ${x(lo)})` }} />}
        {vb != null && <div className="absolute top-0 h-full w-0.5 bg-indigo-700" style={{ left: x(vb) }} title={`AI ${vb} µm`} />}
        {measured != null && <div className="absolute -top-0.5 h-4 w-1 rounded bg-gray-900" style={{ left: x(measured) }} title={`วัดจริง ${measured} µm`} />}
      </div>
      <div className="relative h-3 text-[9px] text-gray-400">
        <span className="absolute -translate-x-1/2" style={{ left: x(VB_ACCEL) }}>
          {VB_ACCEL}
        </span>
        <span className="absolute -translate-x-1/2" style={{ left: x(VB_EOL) }}>
          {VB_EOL}
        </span>
        <span className="absolute right-0">{GAUGE_MAX}+ µm</span>
      </div>
    </div>
  );
};

const ZoneProbs: React.FC<{ probs: Record<VbZone, number> }> = ({ probs }) => (
  <div className="flex h-1.5 rounded overflow-hidden" title={ZONES.map((z) => `${ZONE_STYLE[z].th} ${((probs[z] || 0) * 100).toFixed(0)}%`).join(' · ')}>
    {ZONES.map((z) => (
      <div key={z} className={ZONE_STYLE[z].bar} style={{ width: `${(probs[z] || 0) * 100}%` }} />
    ))}
  </div>
);

const um = (v: number | null | undefined, d = 0) => (v == null ? '—' : `${v.toFixed(d)} µm`);
const mean = (xs: (number | null | undefined)[]) => {
  const v = xs.filter((x): x is number => x != null);
  return v.length === xs.length && v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
};
const VERDICT_OF: Record<VbZone, ToolVerdict> = { normal: 'OK', accel: 'MONITOR', eol: 'REPLACE' };

// ───────────────────────────── บริบทจาก Machine Monitoring ─────────────────────────────
const RulContextBar: React.FC<{ ctx: RulContext | null }> = ({ ctx }) =>
  !ctx ? null : (
    <div className="mb-3 p-3 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-700 leading-relaxed space-y-1">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Gauge className="w-3.5 h-3.5 text-slate-500" />
        <b>
          ต่อจาก Machine Monitoring: {ctx.machine_id} · ดอก {ctx.tool_id}
        </b>
        ถอดเมื่อเวลาตัดสะสม {fmt(ctx.t_min)} นาที ({ctx.reason === 'REPLACED_BY_OPERATOR' ? `ผู้ควบคุม ${ctx.removed_by} ถอดดอก` : 'สิ้นสุดข้อมูลการทดลอง'} ·{' '}
        {fmtDateTime(ctx.removed_at)})
      </p>
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
        แบบจำลอง RUL ตอนถอด: <RecBadge rec={ctx.recommendation} /> <WearBadge state={ctx.wear_state} />
        RUL ≈ {fmt(ctx.rul_min)} นาที (P10–P90 {fmt(ctx.rul_lo)}–{fmt(ctx.rul_hi)}) = คาดว่า VB ใกล้ {VB_EOL} µm
        <span className="text-slate-400">· {ctx.model_version}</span>
      </p>
      {ctx.images_trained_in && (
        <p className="text-amber-700">
          ภาพชุดนี้เคยใช้ retrain แบบจำลองภาพแล้ว ({ctx.images_trained_in.join(', ')}) — เป็นการเล่นซ้ำดอกเดิมหลังรีเซ็ตสตรีม ผลของ AI รอบนี้จึงไม่ใช่การทดสอบกับภาพใหม่
        </p>
      )}
    </div>
  );

// ───────────────────────────── สถานีตรวจ ─────────────────────────────
const STEPS = ['ใช้งานบนเครื่อง', 'RUL แจ้งหมดอายุ', 'ถอดดอก + AI วัด VB', 'ผู้ตรวจยืนยัน', 'เปลี่ยนใบมีด'];
const openRep = (b: VisionBlade) => b.replace_status === 'REQUIRED' || b.replace_status === 'ADVISED';

const stationStep = (s: VisionStation): number => {
  const ins = s.cycle_inspection;
  if (ins?.status === 'VERIFIED') return ins.blades?.some(openRep) ? 4 : 5;
  if (ins) return 3;
  if (s.rul?.state === 'COMPLETED') return 2;
  if (s.rul?.state === 'HOLD' || s.rul?.recommendation === 'REPLACE_NOW') return 1;
  return 0;
};

const StationsTab: React.FC<{ onOpen: (id: string) => void; onTab: (t: Tab) => void; reloadKey: number }> = ({
  onOpen,
  onTab,
  reloadKey,
}) => {
  const [stations, setStations] = useState<VisionStation[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => api.getVisionStations().then(setStations).catch((e) => setErr(e.message)), []);
  useEffect(() => {
    load();
    const t = setInterval(load, 5000); // สถานะ RUL ของดอกบนเครื่องเปลี่ยนตลอด
    return () => clearInterval(t);
  }, [load, reloadKey]);

  const capture = async (m: number) => {
    setBusy(m);
    setErr(null);
    try {
      const ins = await api.captureInspection(m);
      onOpen(ins.id);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="p-3 rounded-lg bg-indigo-50/60 border border-indigo-100 text-xs text-indigo-900 leading-relaxed">
        <b>ต่อจาก Machine Monitoring:</b> เมื่อแบบจำลอง RUL แจ้งว่าดอกของเครื่องหมดอายุ (REPLACE_NOW) และผู้ควบคุมกด “ถอดดอก” → ระบบถ่ายภาพหน้าคมมีด 4 ใบ (B1–B4)
        → AI <b>วัดรอยสึกด้านข้าง VB (µm)</b> ของแต่ละใบ แล้วเทียบเกณฑ์เดียวกับแบบจำลอง RUL: ปกติ &lt; {VB_ACCEL} µm · ใกล้หมดอายุ {VB_ACCEL}–{VB_EOL} µm · หมดอายุ ≥ {VB_EOL} µm
        → ผู้ตรวจยืนยัน/วัดจริง → ใบสั่งเปลี่ยนใบมีดให้วิศวกร
        <span className="text-indigo-700/80">
          {' '}
          · ข้อมูลเซนเซอร์ของ M1/M2/M3 คือดอก LUH T3/T6/T9 และภาพใบมีดคือภาพช่วงท้ายอายุของดอก Nonastreda N8/N9/N10 ที่สึกเท่ากับดอกจริงตอนถอด — ทั้งคู่ไม่เคยใช้ฝึกแบบจำลอง
        </span>
      </div>
      {err && <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{err}</div>}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {stations.map((s) => {
          const step = stationStep(s);
          const ins = s.cycle_inspection;
          const r = s.rul;
          const orderReq = ins?.blades?.some((b) => b.replace_status === 'REQUIRED');
          const orderAdv = ins?.blades?.some((b) => b.replace_status === 'ADVISED');
          const toolMean = ins ? ins.final_summary?.mean_vb ?? ins.ai_summary?.mean_vb : null;
          return (
            <div key={s.machine} className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 flex flex-col gap-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-bold text-gray-900">
                    {s.machine_id} <span className="text-xs font-normal text-gray-400">· ดอก {s.tool_id ?? '—'} · 4 ใบมีด</span>
                  </p>
                  <p className="text-[11px] text-gray-500">{r?.state ? <StreamBadge state={r.state} /> : 'ไม่มีข้อมูลจาก Machine Monitoring'}</p>
                </div>
                {ins && <VerdictChip v={ins.final_verdict || ins.ai_verdict} />}
              </div>

              {r && r.state !== 'COMPLETED' && (
                <div className="rounded-lg bg-gray-50 p-2.5 text-[11px] space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-500">RUL จาก Machine Monitoring</span>
                    {r.recommendation && <RecBadge rec={r.recommendation} />}
                  </div>
                  {r.rul_min == null ? (
                    <p className="text-gray-500">ยังไม่มีค่าพยากรณ์ (ช่วงเริ่มใช้งานดอก) · เวลาตัด {fmt(r.t_min)} นาที</p>
                  ) : (
                    <p className="tabular-nums">
                      <b className="text-base">{fmt(r.rul_min)}</b> นาที (P10 {fmt(r.rul_lo)}) · เวลาตัด {fmt(r.t_min)} นาที
                      {r.life_used_pct != null && ` · ใช้อายุ ${r.life_used_pct.toFixed(0)}%`}
                    </p>
                  )}
                </div>
              )}

              <ol className="flex items-center gap-1">
                {STEPS.map((label, i) => (
                  <li key={label} className="flex-1" title={label}>
                    <div className={`h-1.5 rounded-full ${i < step ? 'bg-indigo-500' : i === step ? 'bg-amber-400 animate-pulse' : 'bg-gray-200'}`} />
                  </li>
                ))}
              </ol>
              <p className="text-[11px] text-gray-600 -mt-1">
                ขั้นที่ {Math.min(step + 1, STEPS.length)}/{STEPS.length}: <b>{step >= STEPS.length ? 'ใบมีดพร้อมใช้งาน' : STEPS[step]}</b>
              </p>

              {step === 0 && <p className="text-[11px] text-gray-500">ดอกกำลังใช้งาน — ระบบจะถ่ายภาพและวัด VB เมื่อ Machine Monitoring แจ้งหมดอายุและผู้ควบคุมถอดดอก</p>}
              {step === 1 && (
                <Link to={`/machine-monitoring?machine=${s.machine}`} className="btn-danger justify-center">
                  <Gauge className="w-3.5 h-3.5" /> RUL แจ้งเปลี่ยนดอกทันที — ไปถอดดอกที่ Machine Monitoring
                </Link>
              )}
              {step === 2 && (
                <button disabled={!s.can_capture || busy !== null} onClick={() => capture(s.machine)} className="btn-primary justify-center">
                  <Camera className={`w-3.5 h-3.5 ${busy === s.machine ? 'animate-pulse' : ''}`} />
                  {busy === s.machine ? 'กำลังถ่ายภาพและวัด VB…' : 'ถ่ายภาพ 4 ใบมีดของดอกที่ถอด'}
                </button>
              )}
              {ins && (
                <>
                  <div className="grid grid-cols-4 gap-1.5">
                    {ins.blades?.map((b) => {
                      const vb = b.final_vb ?? b.pred_vb;
                      const z = vb != null ? zoneOf(vb) : null;
                      return (
                        <div key={b.id} className="rounded-md overflow-hidden border border-gray-200">
                          <AuthImage src={b.image_url} alt={`B${b.blade}`} className="w-full h-12 object-cover bg-gray-100" />
                          <p className={`text-[9px] text-center font-bold py-0.5 ${z ? ZONE_STYLE[z].solid : 'bg-gray-200'}`}>
                            B{b.blade} {vb != null ? `${vb.toFixed(0)} µm` : '—'}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-[11px] -mt-1">
                    VB เฉลี่ย 4 ใบ <b>{um(toolMean)}</b> {toolMean != null && <ZoneChip zone={zoneOf(toolMean)} />}
                  </p>
                  <p className="text-[10px] text-gray-400 -mt-1.5">
                    {ins.id} · ถอดที่ {fmt(ins.rul_context?.t_min)} นาที · {ins.status === 'VERIFIED' ? `ยืนยันโดย ${ins.reviewed_by}` : 'ค่า AI รอผู้ตรวจยืนยัน'}
                  </p>
                  {ins.status === 'PENDING_REVIEW' ? (
                    <button onClick={() => onOpen(ins.id)} className="btn-primary justify-center">
                      <ClipboardCheck className="w-3.5 h-3.5" /> ไปยืนยันค่า VB
                    </button>
                  ) : orderReq || orderAdv ? (
                    <button onClick={() => onTab('replace')} className={`${orderReq ? 'btn-danger' : 'btn-secondary'} justify-center`}>
                      <Wrench className="w-3.5 h-3.5" /> ใบสั่งงาน: {orderReq ? 'ต้องเปลี่ยน/ลับดอก' : 'ควรเปลี่ยนดอกตามแผน'}
                    </button>
                  ) : (
                    <p className="text-[11px] text-emerald-700 font-semibold flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> ใบมีดพร้อม — ติดตั้งดอกกลับเข้าเครื่องได้ (Machine Monitoring)
                    </p>
                  )}
                </>
              )}
              <p className="text-[10px] text-gray-400 mt-auto pt-1 border-t border-gray-50">
                รอยืนยันทั้งหมด {s.pending_review} · ใบสั่งงานค้าง {s.open_replacements}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ───────────────────────────── รอตรวจสอบ ─────────────────────────────
type Decision = { source: VbSource; vb: number | null; bench?: BenchMeasurement };

const BladeReview: React.FC<{
  b: VisionBlade;
  d: Decision;
  readonly: boolean;
  measuring: boolean;
  worst: boolean;
  onZoom: () => void;
  onChange: (d: Decision) => void;
  onMeasure: () => void;
}> = ({ b, d, readonly, measuring, worst, onZoom, onChange, onMeasure }) => {
  const finalVb = readonly ? b.final_vb : d.vb;
  const fz = finalVb != null ? zoneOf(finalVb) : null;
  const bench = readonly ? b.metrology : d.bench;
  const measured = readonly ? (b.vb_source !== 'AI' ? b.final_vb : null) : d.source !== 'AI' ? d.vb : null;
  const err = measured != null && b.pred_vb != null ? b.pred_vb - measured : null;
  return (
    <div className={`rounded-xl border overflow-hidden ${fz === 'eol' ? 'border-red-300' : fz === 'accel' ? 'border-amber-300' : 'border-gray-200'}`}>
      <button onClick={onZoom} className="block w-full">
        <AuthImage src={b.image_url} alt={`B${b.blade}`} className="w-full h-28 object-cover bg-gray-100 hover:opacity-90" />
      </button>
      <div className="p-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-bold text-sm">
            ใบมีด B{b.blade} {worst && <span className="ml-1 px-1.5 py-0.5 rounded bg-gray-900 text-white text-[9px] font-semibold">สึกมากสุด</span>}
          </span>
          <ZoneChip zone={b.zone} />
        </div>
        <div>
          <p className="text-[10px] text-gray-500">AI วัดรอยสึก VB</p>
          <p className="text-lg font-bold tabular-nums leading-tight">
            {um(b.pred_vb)} <span className="text-[11px] font-normal text-gray-500">P10–P90 {b.vb_lo?.toFixed(0)}–{b.vb_hi?.toFixed(0)}</span>
          </p>
        </div>
        <VbGauge vb={b.pred_vb} lo={b.vb_lo} hi={b.vb_hi} measured={measured} />
        <div>
          <ZoneProbs probs={b.probs} />
          <p className="text-[10px] text-gray-500 mt-0.5">
            โอกาสเกิน {VB_EOL} µm {((b.probs.eol || 0) * 100).toFixed(0)}% · มั่นใจในโซน {(b.confidence * 100).toFixed(0)}%
          </p>
        </div>
        {b.near_threshold && !readonly && d.source === 'AI' && (
          <p className="text-[10px] text-amber-700 bg-amber-50 rounded px-2 py-1">ช่วงความไม่แน่นอนคร่อมเกณฑ์ — แนะนำวัดยืนยันบน optical bench</p>
        )}

        {readonly ? (
          <div className="text-[11px] rounded-md bg-gray-50 p-2 space-y-0.5">
            <p>
              ค่าที่ใช้ตัดสิน <b>{um(b.final_vb, 1)}</b> ({b.vb_source ? SOURCE_TEXT[b.vb_source] : '—'}) → <ZoneChip zone={b.final_zone} />
            </p>
            {err != null && <p className="text-gray-500">AI คลาด {err > 0 ? '+' : ''}{err.toFixed(1)} µm</p>}
            {bench && (
              <p className="text-gray-500">
                gaps {bench.gaps_um.toFixed(0)} µm · overhang {bench.overhang_um.toFixed(0)} µm
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-1.5">
            <p className="text-[10px] text-gray-500">ผู้ตรวจ: ค่า VB ที่ใช้ตัดสิน</p>
            <div className="grid grid-cols-3 gap-1">
              {(['AI', 'BENCH', 'MANUAL'] as VbSource[]).map((src) => (
                <button
                  key={src}
                  disabled={measuring}
                  onClick={() => {
                    if (src === 'AI') onChange({ source: 'AI', vb: b.pred_vb, bench: d.bench });
                    else if (src === 'BENCH') d.bench ? onChange({ source: 'BENCH', vb: d.bench.flank_wear_um, bench: d.bench }) : onMeasure();
                    else onChange({ source: 'MANUAL', vb: d.vb, bench: d.bench });
                  }}
                  className={`py-1 rounded-md text-[10px] font-bold border transition flex items-center justify-center gap-1 ${
                    d.source === src ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm' : 'bg-white text-gray-500 border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  {src === 'AI' ? <Cpu className="w-3 h-3" /> : src === 'BENCH' ? <Microscope className="w-3 h-3" /> : <Ruler className="w-3 h-3" />}
                  {src === 'AI' ? 'ใช้ค่า AI' : src === 'BENCH' ? (measuring ? 'กำลังวัด…' : 'วัด bench') : 'กรอกเอง'}
                </button>
              ))}
            </div>
            {d.source === 'MANUAL' && (
              <label className="flex items-center gap-1.5 text-[11px]">
                VB
                <input
                  type="number"
                  min={0}
                  max={999}
                  step={0.1}
                  value={d.vb ?? ''}
                  onChange={(e) => onChange({ ...d, vb: e.target.value === '' ? null : Number(e.target.value) })}
                  className="w-20 border border-gray-200 rounded px-1.5 py-0.5 tabular-nums"
                />
                µm (จากกล้องจุลทรรศน์ของผู้ตรวจ)
              </label>
            )}
            {d.source === 'BENCH' && d.bench && (
              <p className="text-[10px] text-gray-600">
                optical bench: VB <b>{d.bench.flank_wear_um.toFixed(1)} µm</b> · gaps {d.bench.gaps_um.toFixed(0)} · overhang {d.bench.overhang_um.toFixed(0)} µm
              </p>
            )}
            <p className={`text-[11px] font-semibold ${fz === 'eol' ? 'text-red-700' : fz === 'accel' ? 'text-amber-700' : 'text-emerald-700'}`}>
              {finalVb != null && fz ? `ใบนี้ ${finalVb.toFixed(1)} µm (${ZONE_STYLE[fz].th}${fz === 'eol' ? ' — เกิน 140 µm เฉพาะใบ' : ''})` : 'กรอกค่า VB'}
              {err != null && <span className="font-normal text-gray-500"> · AI คลาด {err > 0 ? '+' : ''}{err.toFixed(1)} µm (เข้า pool retrain)</span>}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

const ReviewTab: React.FC<{ selected: string | null; onSelect: (id: string | null) => void; onDone: () => void; reloadKey: number }> = ({
  selected,
  onSelect,
  onDone,
  reloadKey,
}) => {
  const [pending, setPending] = useState<VisionInspection[]>([]);
  const [recent, setRecent] = useState<VisionInspection[]>([]);
  const [ins, setIns] = useState<VisionInspection | null>(null);
  const [dec, setDec] = useState<Record<number, Decision>>({});
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [measuring, setMeasuring] = useState<number | null>(null);
  const [zoom, setZoom] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [p, r] = await Promise.all([api.getInspections('PENDING_REVIEW'), api.getInspections('VERIFIED', undefined, 10)]);
    // ใบที่ AI ไม่มั่นใจหรือวัดได้ว่าหมดอายุ ขึ้นก่อน
    p.sort((a, b) => Number(!!b.low_confidence) - Number(!!a.low_confidence) || (b.ai_summary?.mean_vb ?? 0) - (a.ai_summary?.mean_vb ?? 0));
    setPending(p);
    setRecent(r);
    if (!selected && p.length) onSelect(p[0].id);
  }, [selected, onSelect]);

  useEffect(() => {
    load().catch((e) => setErr(e.message));
  }, [load, reloadKey]);

  useEffect(() => {
    if (!selected) {
      setIns(null);
      return;
    }
    api.getInspection(selected).then((d) => {
      setIns(d);
      setDec(Object.fromEntries((d.blades || []).map((b) => [b.blade, { source: 'AI' as VbSource, vb: b.pred_vb }])));
      setNote(d.note || '');
    });
  }, [selected]);

  const measure = async (blade: number) => {
    if (!ins) return;
    setMeasuring(blade);
    setErr(null);
    try {
      const m = await api.measureBlade(ins.id, blade);
      setDec((p) => ({ ...p, [blade]: { source: 'BENCH', vb: m.flank_wear_um, bench: m } }));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setMeasuring(null);
    }
  };

  const submit = async () => {
    if (!ins) return;
    setBusy(true);
    setErr(null);
    try {
      await api.reviewInspection(
        ins.id,
        Object.entries(dec).map(([k, v]) => ({ blade: Number(k), source: v.source, vb_um: v.source === 'MANUAL' ? v.vb : null })),
        note,
      );
      onSelect(null);
      await load();
      onDone();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const readonly = ins?.status !== 'PENDING_REVIEW';
  const finals = Object.entries(dec).map(([k, v]) => ({ blade: Number(k), vb: v.vb }));
  const nMeasured = Object.values(dec).filter((v) => v.source !== 'AI').length;
  const complete = finals.length > 0 && finals.every((f) => f.vb != null && f.vb > 0);
  const liveMean = mean(finals.map((f) => f.vb));             // ระดับดอก = VB เฉลี่ย 4 ใบ (นิยามเดียวกับ RUL)
  const verdict: ToolVerdict | null = liveMean != null ? VERDICT_OF[zoneOf(liveMean)] : null;
  const over = finals.filter((f) => f.vb != null && f.vb >= VB_EOL).map((f) => `B${f.blade}`);
  const worstBlade = readonly
    ? ins?.final_summary?.worst_blade ?? ins?.ai_summary?.worst_blade
    : finals.reduce<{ blade: number; vb: number } | null>((w, f) => (f.vb != null && (!w || f.vb > w.vb) ? { blade: f.blade, vb: f.vb } : w), null)?.blade;
  const ai = ins?.ai_summary;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
      <div className="space-y-4">
        <Card title={`รอตรวจสอบ (${pending.length})`}>
          {pending.length === 0 ? (
            <p className="text-xs text-gray-400">ไม่มีงานค้าง</p>
          ) : (
            <ul className="space-y-1.5">
              {pending.map((p) => (
                <li key={p.id}>
                  <button
                    onClick={() => onSelect(p.id)}
                    className={`w-full text-left px-2.5 py-2 rounded-lg border text-xs ${selected === p.id ? 'border-indigo-300 bg-indigo-50' : 'border-gray-100 hover:bg-gray-50'}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold">
                        {p.machine_id} · ดอก {p.tool_ref}
                      </span>
                      <VerdictChip v={p.ai_verdict} />
                    </div>
                    <p className="text-[10px] text-gray-400 mt-0.5">
                      AI VB เฉลี่ย {um(p.ai_summary?.mean_vb)} · ถอดที่ {fmt(p.rul_context?.t_min)} นาที
                      {p.low_confidence && <span className="ml-1 text-amber-600 font-semibold">· AI ไม่มั่นใจ</span>}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="ยืนยันล่าสุด">
          <ul className="space-y-1.5 text-xs">
            {recent.map((r) => (
              <li key={r.id}>
                <button onClick={() => onSelect(r.id)} className="w-full text-left flex items-center justify-between hover:bg-gray-50 rounded px-1 py-0.5">
                  <span>
                    {r.machine_id} · {r.tool_ref} · เฉลี่ย {um(r.final_summary?.mean_vb)}
                  </span>
                  <VerdictChip v={r.final_verdict} />
                </button>
              </li>
            ))}
            {recent.length === 0 && <li className="text-gray-400">—</li>}
          </ul>
        </Card>
      </div>

      <div className="xl:col-span-3">
        {!ins ? (
          <Card>
            <p className="text-sm text-gray-400 py-10 text-center">เลือกรายการทางซ้ายเพื่อยืนยันค่า VB</p>
          </Card>
        ) : (
          <Card
            title={
              <span>
                {ins.id} · {ins.machine_id} · ดอก {ins.tool_ref} (ถอดจากเครื่อง)
              </span>
            }
            right={
              <span className="text-[11px] text-gray-500">
                ภาพตอนถอดดอก · {fmtDateTime(ins.captured_at)} · {ins.model_version}
              </span>
            }
          >
            {err && <div className="mb-3 p-2 rounded bg-red-50 border border-red-200 text-xs text-red-700">{err}</div>}
            <RulContextBar ctx={ins.rul_context} />
            {ai && (
              <div className="mb-3 p-3 rounded-lg border border-indigo-100 bg-indigo-50/50 grid grid-cols-1 md:grid-cols-3 gap-3 items-center">
                <div>
                  <p className="text-[10px] text-gray-500">ระดับดอก (ใช้ตัดสิน) = VB เฉลี่ย 4 ใบ · AI</p>
                  <p className="text-xl font-bold tabular-nums leading-tight">
                    {um(ai.mean_vb)} <span className="text-[11px] font-normal text-gray-500">P10–P90 {ai.mean_lo.toFixed(0)}–{ai.mean_hi.toFixed(0)}</span>
                  </p>
                  <p className="text-[10px] text-gray-500">
                    โอกาสเฉลี่ยเกิน {VB_EOL} µm {(((ai.probs?.eol ?? 0) as number) * 100).toFixed(0)}% · สึกมากสุด B{ai.worst_blade} {um(ai.worst_vb)}
                  </p>
                </div>
                <VbGauge vb={ai.mean_vb} lo={ai.mean_lo} hi={ai.mean_hi} measured={readonly ? ins.final_summary?.mean_vb : nMeasured ? liveMean : null} />
                <div className="text-[11px] text-gray-600 space-y-1">
                  <p>
                    AI: <VerdictChip v={ins.ai_verdict} />
                    {ins.low_confidence && <span className="ml-1 text-amber-700">ช่วงคร่อมเกณฑ์ — ควรวัดยืนยันบางใบ</span>}
                  </p>
                  <p className="text-[10px] text-gray-400">
                    เกณฑ์เดียวกับ RUL: ชุดข้อมูลเซนเซอร์วัด VB ทุกคมแล้วเฉลี่ย · ISO 8688-2 เฉลี่ยทุกฟันสำหรับรอยสึกสม่ำเสมอ
                  </p>
                </div>
              </div>
            )}
            {ins.blades?.some((b) => b.pred_vb == null) ? (
              <p className="text-sm text-amber-700 py-6 text-center">รายการนี้ยังไม่มีค่า VB จากแบบจำลอง (รอโหลดแบบจำลองวัด VB)</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-4 gap-3">
                {ins.blades?.map((b) => (
                  <BladeReview
                    key={b.id}
                    b={b}
                    d={dec[b.blade] ?? { source: 'AI', vb: b.pred_vb }}
                    readonly={readonly}
                    measuring={measuring === b.blade}
                    worst={worstBlade === b.blade}
                    onZoom={() => setZoom(b.image_url)}
                    onChange={(d) => setDec((p) => ({ ...p, [b.blade]: d }))}
                    onMeasure={() => measure(b.blade)}
                  />
                ))}
              </div>
            )}
            {!readonly ? (
              <div className="mt-4 flex flex-col md:flex-row md:items-center gap-3">
                <input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="หมายเหตุ (ถ้ามี) เช่น พบรอยบิ่นที่ปลายคม"
                  className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-xs"
                />
                <span className="text-xs text-gray-600">
                  ระดับดอก: VB เฉลี่ย <b>{um(liveMean, 1)}</b> → <VerdictChip v={verdict} />
                  {over.length > 0 && <span className="text-red-700"> · เกิน 140 µm เฉพาะใบ {over.join(', ')}</span>} · วัดจริง {nMeasured}/4 ใบ
                </span>
                <button onClick={submit} disabled={busy || !complete || measuring !== null} className="btn-primary">
                  <ClipboardCheck className="w-3.5 h-3.5" /> ยืนยันผล → {verdict === 'OK' ? 'ใช้ดอกต่อ' : 'ออกใบสั่งงาน'}
                </button>
              </div>
            ) : (
              <p className="mt-3 text-xs text-gray-500">
                ยืนยันแล้วโดย {ins.reviewed_by} · {fmtDateTime(ins.reviewed_at)} · ระดับดอก VB เฉลี่ย {um(ins.final_summary?.mean_vb, 1)} →{' '}
                <VerdictChip v={ins.final_verdict} />
                {ins.note ? ` · ${ins.note}` : ''}
              </p>
            )}
          </Card>
        )}
      </div>
      {zoom && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-6" onClick={() => setZoom(null)}>
          <AuthImage src={zoom} alt="zoom" className="max-w-full max-h-full rounded-lg shadow-2xl" />
        </div>
      )}
    </div>
  );
};

// ───────────────────────────── ใบสั่งงานระดับดอก ─────────────────────────────
const ReplaceTab: React.FC<{ reloadKey: number; onChanged: () => void }> = ({ reloadKey, onChanged }) => {
  const [rep, setRep] = useState<Replacements | null>(null);
  const load = useCallback(() => api.getReplacements().then(setRep), []);
  useEffect(() => {
    load();
  }, [load, reloadKey]);
  const done = async (id: string) => {
    await api.markToolServiced(id);
    await load();
    onChanged();
  };
  if (!rep) return <p className="text-sm text-gray-400">กำลังโหลด…</p>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {rep.open.length === 0 ? (
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-semibold border border-emerald-200">
            <CheckCircle2 className="w-4 h-4" /> ไม่มีดอกที่ต้องเปลี่ยน
          </span>
        ) : (
          rep.open.map((o) => (
            <span
              key={o.inspection_id}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border ${
                o.priority === 'REQUIRED' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-amber-50 text-amber-700 border-amber-200'
              }`}
            >
              <Wrench className="w-4 h-4" /> {o.machine_id} · ดอก {o.tool_ref ?? '—'}: {o.priority === 'REQUIRED' ? 'ต้องเปลี่ยน/ลับดอก' : 'ควรเปลี่ยนตามแผน'}
              {o.mean_vb != null && ` (VB เฉลี่ย ${o.mean_vb.toFixed(0)} µm)`}
            </span>
          ))
        )}
        <button onClick={() => api.downloadReplacementsCsv().catch((err) => alert(err.message))} className="btn-secondary ml-auto">
          <Download className="w-3.5 h-3.5" /> CSV
        </button>
      </div>
      <p className="text-[11px] text-gray-500">
        ใบสั่งงาน 1 ใบต่อดอกที่ถอดตามคำแนะนำของแบบจำลอง RUL — ตัดสินด้วย <b>VB เฉลี่ย 4 ใบ</b> (นิยามเดียวกับ RUL): <b className="text-red-700">ต้องเปลี่ยน/ลับดอก</b> ≥ {VB_EOL} µm ·{' '}
        <b className="text-amber-700">ควรเปลี่ยนตามแผน</b> {VB_ACCEL}–{VB_EOL} µm · VB รายใบบอกคมที่สึกมากสุดและคมที่เกิน {VB_EOL} µm เฉพาะใบ (ตรวจรอยสึกเฉพาะจุด/การเยื้องศูนย์) ·
        ดำเนินการแล้วบันทึก จากนั้นติดตั้งดอกที่ Machine Monitoring
      </p>
      <Card title={`ใบสั่งงานค้าง (${rep.open.length})`}>
        <OrderTable items={rep.open} action={(o) => <button onClick={() => done(o.inspection_id)} className="btn-primary">บันทึกว่าดำเนินการแล้ว</button>} />
      </Card>
      <Card title={`ประวัติ (${rep.done.length})`}>
        <OrderTable items={rep.done} action={(o) => <span className="text-[11px] text-gray-500">{o.replaced_by} · {fmtDateTime(o.replaced_at)}</span>} />
      </Card>
    </div>
  );
};

const OrderTable: React.FC<{ items: WorkOrder[]; action: (o: WorkOrder) => React.ReactNode }> = ({ items, action }) =>
  items.length === 0 ? (
    <p className="text-xs text-gray-400">—</p>
  ) : (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-gray-500 border-b border-gray-100">
            <th className="py-2 pr-2">เครื่อง / ดอก</th>
            <th className="py-2 pr-2">ระดับ</th>
            <th className="py-2 pr-2">VB เฉลี่ย</th>
            <th className="py-2 pr-2">VB รายใบ (คมที่สึกมากสุด = กรอบดำ)</th>
            <th className="py-2 pr-2">ถอดตาม RUL</th>
            <th className="py-2 pr-2">รายการตรวจ</th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody>
          {items.map((o) => (
            <tr key={o.inspection_id} className="border-b border-gray-50 align-top">
              <td className="py-2 pr-2 font-semibold">
                {o.machine_id} · {o.tool_ref ?? '—'}
              </td>
              <td className="py-2 pr-2">
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${o.priority === 'REQUIRED' ? 'bg-red-600 text-white' : 'bg-amber-500 text-white'}`}>
                  {o.priority === 'REQUIRED' ? 'ต้องเปลี่ยน/ลับดอก' : 'ควรเปลี่ยนตามแผน'}
                </span>
              </td>
              <td className="py-2 pr-2 tabular-nums font-bold">{um(o.mean_vb, 1)}</td>
              <td className="py-2 pr-2">
                <div className="flex gap-1">
                  {o.blades.map((b) => {
                    const z = b.final_vb != null ? zoneOf(b.final_vb) : null;
                    return (
                      <div
                        key={b.blade}
                        title={`${b.vb_source ? SOURCE_TEXT[b.vb_source] : ''}${b.pred_vb != null && b.vb_source !== 'AI' ? ` · AI ${b.pred_vb.toFixed(0)} µm` : ''}`}
                        className={`rounded overflow-hidden border-2 ${o.worst_blade === b.blade ? 'border-gray-900' : 'border-transparent'}`}
                      >
                        <AuthImage src={b.image_url} alt="" className="w-14 h-6 object-cover" />
                        <p className={`text-[9px] text-center font-bold ${z ? ZONE_STYLE[z].solid : 'bg-gray-200'}`}>
                          B{b.blade} {b.final_vb != null ? b.final_vb.toFixed(0) : '—'}
                        </p>
                      </div>
                    );
                  })}
                </div>
                {o.over_limit.length > 0 && <p className="text-[10px] text-red-700 mt-0.5">เกิน {VB_EOL} µm เฉพาะใบ: {o.over_limit.map((b) => `B${b}`).join(', ')}</p>}
              </td>
              <td className="py-2 pr-2 text-gray-500">
                {fmt(o.removed_t_min)} นาที {o.rul_recommendation && <RecBadge rec={o.rul_recommendation} />}
                <br />
                {o.removed_by}
              </td>
              <td className="py-2 pr-2 text-gray-500">
                {o.inspection_id}
                <br />
                ยืนยันโดย {o.reviewed_by}
              </td>
              <td className="py-2 text-right">{action(o)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

// ───────────────────────────── โมเดล & retrain ─────────────────────────────
const MetricBox: React.FC<{ label: string; m?: { mae?: number; zone_acc?: number; n?: number } | null; hint?: string }> = ({ label, m, hint }) => (
  <div className="rounded-lg bg-gray-50 p-2 text-center" title={hint}>
    <p className="text-[10px] text-gray-500">{label}</p>
    {m?.mae != null ? (
      <p className="font-bold">
        {m.mae.toFixed(1)} µm <span className="text-[10px] font-normal text-gray-400">โซนถูก {m.zone_acc?.toFixed(0)}%</span>
      </p>
    ) : (
      <p className="text-[11px] text-gray-400 mt-1">—</p>
    )}
  </div>
);

const ModelTab: React.FC<{ isAdmin: boolean; reloadKey: number; onChanged: () => void }> = ({ isAdmin, reloadKey, onChanged }) => {
  const [model, setModel] = useState<VisionModelInfo | null>(null);
  const [stats, setStats] = useState<VisionStats | null>(null);
  const [pool, setPool] = useState<TrainingPool | null>(null);
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [versions, setVersions] = useState<VisionVersion[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [m, s, p, j, v] = await Promise.all([
      api.getVisionModel(),
      api.getVisionStats(),
      api.getTrainingPool(),
      api.getTrainingJobs().catch(() => [] as TrainingJob[]),
      api.getVisionVersions().catch(() => [] as VisionVersion[]),
    ]);
    setModel(m);
    setStats(s);
    setPool(p);
    setJobs(j);
    setVersions(v);
  }, []);

  useEffect(() => {
    load().catch((e) => setErr(e.message));
  }, [load, reloadKey]);

  const running = jobs.some((j) => j.status === 'QUEUED' || j.status === 'RUNNING');
  const live = jobs.find((j) => (j.status === 'QUEUED' || j.status === 'RUNNING') && j.progress?.history?.length);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => load().catch(() => {}), 3000);
    return () => clearInterval(t);
  }, [running, load]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      await load();
      onChanged();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const meta = model?.meta;
  const mt = meta?.metrics;
  return (
    <div className="space-y-4">
      {err && <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{err}</div>}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card
          title={
            <span className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-500" /> แบบจำลองวัด VB ที่ใช้งาน (MinIO)
            </span>
          }
        >
          {!model ? (
            <p className="text-xs text-gray-400">—</p>
          ) : (
            <div className="space-y-1.5 text-xs">
              <p className="text-sm font-bold">{model.version || 'ไม่มี'}</p>
              {model.error && <p className="text-red-600">{model.error}</p>}
              <p className="text-gray-500">
                {meta?.model} · {meta?.n_params ? `${(meta.n_params / (meta.ensemble || 1) / 1e6).toFixed(2)}M params${(meta.ensemble || 1) > 1 ? '/ตัว' : ''}` : ''} · อินพุต {meta?.image_size?.join('×')}
              </p>
              <p className="text-gray-500">
                ฝึก: ดอก {meta?.train_tools?.join(', ')} + ค่าวัดจากคน {meta?.n_human_labels ?? 0} ใบ · val: ดอก {meta?.val_tools?.join(', ')} · test: ดอก {meta?.test_tools?.join(', ')}
              </p>
              <div className="grid grid-cols-2 gap-2 pt-1">
                <MetricBox label="Cross-validation (ดอก 1–7)" m={meta?.cv} hint="leave-one-tool-out ใช้เลือกแบบจำลอง" />
                <MetricBox label="Validation (ดอก 7)" m={mt?.val} />
                <MetricBox label="Test ดอกบนเครื่อง (8–10)" m={mt?.test} />
                <MetricBox label={meta?.metrics?.recent ? 'ค่าที่วัดล่าสุด (คน)' : 'Test เฉพาะภาพตอนถอดดอก'} m={mt?.recent || mt?.test_eol_runs} />
              </div>
              {meta?.interval && (
                <p className="text-[10px] text-gray-400">
                  ช่วง P10–P90 = ค่าทาย {meta.interval.q_lo >= 0 ? '+' : ''}
                  {meta.interval.q_lo} / +{meta.interval.q_hi} µm (จาก residual นอกชุดฝึก) · CPU {meta.cpu_latency_ms_per_image} ms/ภาพ
                </p>
              )}
              <p className="text-[10px] text-gray-400">
                sha256 {model.sha256?.slice(0, 16)}… · โหลด {fmtDateTime(model.loaded_at)}
              </p>
            </div>
          )}
        </Card>
        <Card
          title={
            <span className="flex items-center gap-2">
              <ScanEye className="w-4 h-4 text-indigo-500" /> AI เทียบค่าที่วัดจริง
            </span>
          }
        >
          {!stats || stats.reviewed_blades === 0 ? (
            <p className="text-xs text-gray-400">ยังไม่มีผลที่ยืนยัน</p>
          ) : (
            <div className="text-xs space-y-2">
              <p>
                วัดจริง {stats.measured_blades} ใบ · ยอมรับค่า AI {stats.accepted_blades} ใบ
              </p>
              {stats.mae_um != null ? (
                <p>
                  AI คลาดจากค่าวัดจริงเฉลี่ย <b className="text-lg">{stats.mae_um} µm</b> (bias {stats.bias_um! > 0 ? '+' : ''}
                  {stats.bias_um} µm) · โซนตรงกัน {stats.zone_agreement_pct}%
                </p>
              ) : (
                <p className="text-gray-400">ยังไม่มีใบที่วัดจริง (การยอมรับค่า AI ไม่บอกว่า AI ถูกหรือผิด)</p>
              )}
              {stats.measured_blades > 0 && (
                <table className="w-full text-center">
                  <thead>
                    <tr className="text-[10px] text-gray-500">
                      <th className="text-left">วัดจริง \ AI</th>
                      {ZONES.map((z) => (
                        <th key={z}>{ZONE_STYLE[z].th}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {ZONES.map((t) => (
                      <tr key={t}>
                        <td className="text-left text-[10px] text-gray-500">{ZONE_STYLE[t].th}</td>
                        {ZONES.map((p) => (
                          <td key={p} className={`py-1 tabular-nums ${t === p ? 'font-bold text-emerald-700 bg-emerald-50' : stats.confusion_measured_vs_ai[t][p] ? 'text-red-600' : 'text-gray-300'}`}>
                            {stats.confusion_measured_vs_ai[t][p]}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </Card>
        <Card
          title={
            <span className="flex items-center gap-2">
              <RefreshCw className="w-4 h-4 text-indigo-500" /> Retrain pool
            </span>
          }
        >
          {pool && (
            <div className="text-xs space-y-2">
              <p>
                ค่า VB ที่วัดจริงและยังไม่เคยใช้ฝึก <b>{pool.n_labels}</b> ใบ · AI คลาด &gt; {pool.large_error_um} µm <b className="text-amber-700">{pool.n_large_error}</b> ใบ
              </p>
              <div className="h-2 rounded bg-gray-100 overflow-hidden">
                <div className="h-full bg-amber-500" style={{ width: `${Math.min(100, (pool.n_large_error / pool.threshold) * 100)}%` }} />
              </div>
              <p className="text-[11px] text-gray-500">
                {pool.suggest_retrain ? 'แนะนำให้ retrain แล้ว' : `แนะนำ retrain เมื่อมีใบที่ AI คลาด > ${pool.large_error_um} µm ≥ ${pool.threshold} ใบ`} · ค่าที่ยอมรับจาก AI ไม่ใช้ฝึก
              </p>
              <button
                disabled={!isAdmin || busy || running || pool.n_labels === 0}
                onClick={() => act(() => api.startRetrain())}
                className="btn-primary w-full justify-center"
                title={isAdmin ? '' : 'เฉพาะผู้ดูแลระบบ'}
              >
                <RefreshCw className={`w-3.5 h-3.5 ${running ? 'animate-spin' : ''}`} /> {running ? 'กำลัง retrain (GPU worker)…' : 'เริ่ม retrain'}
              </button>
              {!isAdmin && <p className="text-[10px] text-gray-400">ปุ่ม retrain / promote ใช้ได้เฉพาะผู้ดูแลระบบ</p>}
            </div>
          )}
        </Card>
      </div>

      {live?.progress && (
        <Card
          title={`กำลัง retrain ${live.id} — epoch ${live.progress.epoch}/${live.progress.epochs}`}
          right={<Link to="/model-registry?model=vision" className="text-xs text-indigo-600 font-semibold">กราฟทั้งหมดใน Model Registry →</Link>}
        >
          <TrainingCurves history={live.progress.history} epochs={live.progress.epochs_per_member ?? live.progress.epochs} height={150} compact />
        </Card>
      )}
      <Card
        title="งาน retrain และ candidate model"
        right={<Link to="/model-registry?model=vision" className="text-xs text-indigo-600 font-semibold">กราฟการเทรน →</Link>}
      >
        {jobs.length === 0 ? (
          <p className="text-xs text-gray-400">ยังไม่มีงาน retrain</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-gray-500 border-b border-gray-100">
                  <th className="py-2 pr-2">งาน</th>
                  <th className="py-2 pr-2">สถานะ</th>
                  <th className="py-2 pr-2">ค่าวัด (คลาดมาก)</th>
                  <th className="py-2 pr-2">MAE ดอก 7: เดิม → ใหม่</th>
                  <th className="py-2 pr-2">MAE ค่าวัดล่าสุด: เดิม → ใหม่</th>
                  <th className="py-2 pr-2">Gate</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => {
                  const r = j.result;
                  const isVb = r?.metrics?.val?.mae != null;
                  return (
                    <tr key={j.id} className="border-b border-gray-50 align-top">
                      <td className="py-2 pr-2">
                        <p className="font-semibold">{j.id}</p>
                        <p className="text-[10px] text-gray-400">
                          {j.requested_by} · {fmtDateTime(j.requested_at)}
                        </p>
                        {j.candidate_version && <p className="text-[10px] font-mono text-gray-500">{j.candidate_version}</p>}
                      </td>
                      <td className="py-2 pr-2">
                        <span className="font-semibold">{j.status}</span>
                        {j.progress && (j.status === 'RUNNING' || j.status === 'QUEUED') && (
                          <p className="text-[10px] text-amber-700">
                            {j.progress.stage === 'evaluating' ? 'กำลังประเมิน…' : `epoch ${j.progress.epoch}/${j.progress.epochs}`}
                          </p>
                        )}
                        {j.error && <p className="text-[10px] text-red-600 max-w-xs">{j.error}</p>}
                      </td>
                      <td className="py-2 pr-2 tabular-nums">
                        {j.n_labels} ({j.n_large_error})
                      </td>
                      <td className="py-2 pr-2 tabular-nums">{isVb ? `${r!.metrics.base_val.mae} → ${r!.metrics.val.mae} µm` : '—'}</td>
                      <td className="py-2 pr-2 tabular-nums">
                        {isVb && r!.n_recent_eval ? `${r!.metrics.base_recent.mae} → ${r!.metrics.recent.mae} µm (${r!.n_recent_eval} ใบ)` : isVb ? 'ข้อมูลยังน้อย' : '—'}
                      </td>
                      <td className="py-2 pr-2">
                        {r ? (
                          r.gate.passed ? (
                            <span className="text-emerald-700 font-semibold">ผ่าน</span>
                          ) : (
                            <span className="text-red-600 font-semibold" title={r.gate.rule}>
                              ไม่ผ่าน
                            </span>
                          )
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="py-2 text-right whitespace-nowrap">
                        {j.status === 'DONE' && isAdmin && (
                          <div className="flex gap-1 justify-end">
                            <button
                              disabled={busy || !r?.gate.passed || !isVb}
                              onClick={() => act(() => api.decideTrainingJob(j.id, 'promote'))}
                              className="btn-primary"
                              title={r?.gate.passed ? '' : 'ไม่ผ่าน gate'}
                            >
                              Promote
                            </button>
                            <button disabled={busy} onClick={() => act(() => api.decideTrainingJob(j.id, 'reject'))} className="btn-secondary">
                              Reject
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="text-[10px] text-gray-400 mt-2">
              Gate: MAE บนดอก 7 แย่ลงไม่เกิน 1 µm และ MAE บนค่าที่วัดล่าสุด (20% ท้าย ไม่ใช้ฝึก) ต้องไม่แย่กว่าเดิม — candidate ถูกใช้งานเมื่อผู้ดูแลกด Promote เท่านั้น ·
              log การฝึกดูได้ใน TensorBoard (logs/tensorboard)
            </p>
          </div>
        )}
      </Card>

      <Card
        title="เวอร์ชันใน MinIO (models/tool-vision/)"
        right={<Link to="/model-registry?model=vision" className="text-xs text-indigo-600 font-semibold">กราฟการเทรน / สลับเวอร์ชัน →</Link>}
      >
        <ul className="text-xs space-y-1">
          {versions.map((v) => (
            <li key={v.version} className="flex flex-wrap items-center gap-2">
              <span className="font-mono">{v.version}</span>
              {(() => {
                const st = v.active ? VERSION_STATUS.production : VERSION_STATUS[v.status ?? ''] ?? VERSION_STATUS.previous;
                return <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${st.cls}`}>{st.label}</span>;
              })()}
              <span className="text-gray-400">
                {fmtDateTime(v.created_utc)}
                {v.val_mae != null && ` · val MAE ${v.val_mae} µm`}
                {v.test_mae != null && ` · test MAE ${v.test_mae} µm`}
                {` · ค่าวัดจากคน ${v.n_human_labels ?? 0}`}
              </span>
            </li>
          ))}
          {versions.length === 0 && <li className="text-gray-400">—</li>}
        </ul>
      </Card>
    </div>
  );
};

// ───────────────────────────── หน้า ─────────────────────────────
export const ToolVisionPage: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [params, setParams] = useSearchParams();
  const tab = (params.get('tab') as Tab) || 'stations';
  const [selected, setSelected] = useState<string | null>(params.get('inspection'));
  useEffect(() => {
    const id = params.get('inspection');
    if (id) setSelected(id);
  }, [params]);
  const [reloadKey, setReloadKey] = useState(0);
  const [counts, setCounts] = useState({ pending: 0, replace: 0 });
  const [model, setModel] = useState<VisionModelInfo | null>(null);

  const refreshCounts = useCallback(() => {
    api.getVisionStations().then((s) =>
      setCounts({ pending: s.reduce((a, x) => a + x.pending_review, 0), replace: s.reduce((a, x) => a + x.open_replacements, 0) }),
    );
  }, []);
  useEffect(() => {
    refreshCounts();
    api.getVisionModel().then(setModel).catch(() => {});
  }, [refreshCounts, reloadKey]);

  const bump = () => setReloadKey((k) => k + 1);
  const tabs = useMemo(
    () =>
      [
        { id: 'stations', label: 'สถานีตรวจ (จาก Machine Monitoring)', icon: Camera },
        { id: 'review', label: `รอตรวจสอบ${counts.pending ? ` (${counts.pending})` : ''}`, icon: ClipboardCheck },
        { id: 'replace', label: `ใบสั่งงาน${counts.replace ? ` (${counts.replace})` : ''}`, icon: Wrench },
        { id: 'model', label: 'โมเดล & Retrain', icon: RefreshCw },
      ] as const,
    [counts],
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Tool Inspection (Vision)"
        subtitle={`ต่อจาก Machine Monitoring: ดอกที่ RUL แจ้งหมดอายุและถูกถอด → AI วัดรอยสึก VB ของ 4 ใบมีดจากภาพ → VB เฉลี่ย 4 ใบเทียบเกณฑ์ ${VB_ACCEL}/${VB_EOL} µm (เหมือน RUL) → ผู้ตรวจยืนยัน/วัดจริง → ใบสั่งงาน`}
        actions={
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
              model?.status === 'READY' ? 'bg-indigo-50 text-indigo-700 border-indigo-200' : 'bg-red-50 text-red-700 border-red-200'
            }`}
            title={model?.error || ''}
          >
            <ShieldAlert className="w-3.5 h-3.5" /> {model?.status === 'READY' ? `MinIO · ${model.version}` : 'VB model unavailable'}
          </span>
        }
      />
      <div className="flex flex-wrap gap-1 p-1 bg-gray-100 rounded-lg w-fit">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setParams({ tab: t.id })}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 ${tab === t.id ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-800'}`}
          >
            <t.icon className="w-3.5 h-3.5" /> {t.label}
          </button>
        ))}
      </div>
      {tab === 'stations' && (
        <StationsTab
          reloadKey={reloadKey}
          onTab={(t) => setParams({ tab: t })}
          onOpen={(id) => {
            setSelected(id);
            setParams({ tab: 'review', inspection: id });
            refreshCounts();
          }}
        />
      )}
      {tab === 'review' && <ReviewTab selected={selected} onSelect={setSelected} onDone={bump} reloadKey={reloadKey} />}
      {tab === 'replace' && <ReplaceTab reloadKey={reloadKey} onChanged={bump} />}
      {tab === 'model' && <ModelTab isAdmin={isAdmin} reloadKey={reloadKey} onChanged={bump} />}
    </div>
  );
};

export default ToolVisionPage;
