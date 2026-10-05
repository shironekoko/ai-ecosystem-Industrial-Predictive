/**
 * Tool Inspection (Vision) — ขั้นต่อจาก Machine Monitoring
 * RUL แจ้งดอกหมดอายุ → ผู้ควบคุมถอดดอก → ถ่ายภาพ 4 ใบมีด (optical bench) → AI ชี้ใบที่เสีย → ผู้ตรวจยืนยัน/แก้
 * → ใบสั่งเปลี่ยนใบมีดให้วิศวกร · label ที่ยืนยันแล้วเข้า pool → retrain → promote
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Camera,
  CheckCircle2,
  ClipboardCheck,
  Cpu,
  Download,
  Gauge,
  RefreshCw,
  ScanEye,
  ShieldAlert,
  Wrench,
  XCircle,
} from 'lucide-react';
import { PageHeader } from '../../components/common';
import { Card, RecBadge, StreamBadge, WearBadge, fmt, fmtDateTime } from '../../components/toollife/ui';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import type {
  BladeLabel,
  Replacements,
  RulContext,
  ToolVerdict,
  TrainingJob,
  TrainingPool,
  VisionInspection,
  VisionModelInfo,
  VisionStation,
  VisionStats,
  VisionVersion,
} from '../../types';

const LABELS: BladeLabel[] = ['sharp', 'used', 'dulled'];
const LABEL_STYLE: Record<BladeLabel, { th: string; cls: string; bar: string; solid: string }> = {
  sharp: { th: 'คม', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', bar: 'bg-emerald-500', solid: 'bg-emerald-600 text-white border-emerald-600' },
  used: { th: 'ใช้แล้ว', cls: 'bg-amber-50 text-amber-700 border-amber-200', bar: 'bg-amber-500', solid: 'bg-amber-500 text-white border-amber-500' },
  dulled: { th: 'ทื่อ/เสีย', cls: 'bg-red-50 text-red-700 border-red-200', bar: 'bg-red-500', solid: 'bg-red-600 text-white border-red-600' },
};
const VERDICT_STYLE: Record<ToolVerdict, { th: string; cls: string }> = {
  OK: { th: 'ใช้งานต่อได้', cls: 'bg-emerald-600 text-white' },
  MONITOR: { th: 'เฝ้าระวัง', cls: 'bg-amber-500 text-white' },
  REPLACE: { th: 'ต้องเปลี่ยนใบมีด', cls: 'bg-red-600 text-white' },
};
type Tab = 'stations' | 'review' | 'replace' | 'model';

const LabelChip: React.FC<{ label: BladeLabel | null | undefined }> = ({ label }) =>
  label ? (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-semibold border uppercase ${LABEL_STYLE[label].cls}`}>
      {label} · {LABEL_STYLE[label].th}
    </span>
  ) : (
    <span className="text-gray-300">—</span>
  );

const VerdictChip: React.FC<{ v: ToolVerdict | null | undefined }> = ({ v }) =>
  v ? <span className={`inline-flex px-2 py-0.5 rounded-md text-[11px] font-bold ${VERDICT_STYLE[v].cls}`}>{VERDICT_STYLE[v].th}</span> : null;

const ProbBars: React.FC<{ probs: Record<BladeLabel, number> }> = ({ probs }) => (
  <div className="space-y-1">
    {LABELS.map((l) => (
      <div key={l} className="flex items-center gap-2 text-[10px]">
        <span className="w-10 text-gray-500 uppercase">{l}</span>
        <div className="flex-1 h-1.5 rounded bg-gray-100 overflow-hidden">
          <div className={`h-full ${LABEL_STYLE[l].bar}`} style={{ width: `${(probs[l] || 0) * 100}%` }} />
        </div>
        <span className="w-9 text-right tabular-nums text-gray-600">{((probs[l] || 0) * 100).toFixed(0)}%</span>
      </div>
    ))}
  </div>
);

const pct = (v: number | null | undefined, d = 1) => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(d)}%`);

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
        RUL ≈ {fmt(ctx.rul_min)} นาที (P10–P90 {fmt(ctx.rul_lo)}–{fmt(ctx.rul_hi)})
        {ctx.first_replace_now_min != null && <span>· แจ้งเปลี่ยนทันทีครั้งแรกที่ {fmt(ctx.first_replace_now_min)} นาที</span>}
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
const STEPS = ['ใช้งานบนเครื่อง', 'RUL แจ้งหมดอายุ', 'ถอดดอก + ถ่ายภาพ', 'ผู้ตรวจยืนยัน', 'เปลี่ยนใบมีด'];

const stationStep = (s: VisionStation): number => {
  const ins = s.cycle_inspection;
  if (ins?.status === 'VERIFIED') return ins.blades?.some((b) => b.replace_status === 'REQUIRED') ? 4 : 5;
  if (ins) return 3;
  if (s.rul?.state === 'COMPLETED') return 2;
  if (s.rul?.state === 'HOLD' || s.rul?.recommendation === 'REPLACE_NOW') return 1;
  return 0;
};

const StationsTab: React.FC<{ actor: string; onOpen: (id: string) => void; onTab: (t: Tab) => void; reloadKey: number }> = ({
  actor,
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
      const ins = await api.captureInspection(m, actor);
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
        <b>ต่อจาก Machine Monitoring:</b> เมื่อแบบจำลอง RUL แจ้งว่าดอกของเครื่องหมดอายุ (REPLACE_NOW) และผู้ควบคุมกด “ถอดดอก” → ระบบถ่ายภาพหน้าคมมีด 4 ใบ (B1–B4) บน optical bench
        → AI ชี้ว่าใบไหนเสีย → ผู้ตรวจยืนยัน → ใบสั่งเปลี่ยนใบมีดให้วิศวกร
        <span className="text-indigo-700/80">
          {' '}
          · ข้อมูลเซนเซอร์ของ M1/M2/M3 คือดอก LUH T3/T6/T9 และภาพใบมีดคือภาพตอนถอดดอก (รอบสุดท้าย) ของดอก Nonastreda N8/N9/N10 — ทั้งคู่ไม่เคยใช้ฝึกแบบจำลอง
        </span>
      </div>
      {err && <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{err}</div>}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {stations.map((s) => {
          const step = stationStep(s);
          const ins = s.cycle_inspection;
          const r = s.rul;
          const openRep = ins?.blades?.filter((b) => b.replace_status === 'REQUIRED').map((b) => `B${b.blade}`) ?? [];
          return (
            <div key={s.machine} className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 flex flex-col gap-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-bold text-gray-900">
                    {s.machine_id} <span className="text-xs font-normal text-gray-400">· ดอก {s.tool_id ?? '—'} · 4 ใบมีด</span>
                  </p>
                  <p className="text-[11px] text-gray-500">
                    {r?.state ? <StreamBadge state={r.state} /> : 'ไม่มีข้อมูลจาก Machine Monitoring'}
                  </p>
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

              {step === 0 && <p className="text-[11px] text-gray-500">ดอกกำลังใช้งาน — ระบบจะถ่ายภาพใบมีดเมื่อ Machine Monitoring แจ้งหมดอายุและผู้ควบคุมถอดดอก</p>}
              {step === 1 && (
                <Link to={`/machine-monitoring?machine=${s.machine}`} className="btn-danger justify-center">
                  <Gauge className="w-3.5 h-3.5" /> RUL แจ้งเปลี่ยนดอกทันที — ไปถอดดอกที่ Machine Monitoring
                </Link>
              )}
              {step === 2 && (
                <button disabled={!s.can_capture || busy !== null} onClick={() => capture(s.machine)} className="btn-primary justify-center">
                  <Camera className={`w-3.5 h-3.5 ${busy === s.machine ? 'animate-pulse' : ''}`} />
                  {busy === s.machine ? 'กำลังถ่ายภาพและวิเคราะห์…' : 'ถ่ายภาพ 4 ใบมีดของดอกที่ถอด'}
                </button>
              )}
              {ins && (
                <>
                  <div className="grid grid-cols-4 gap-1.5">
                    {ins.blades?.map((b) => {
                      const lab = (b.final_label || b.pred_label) as BladeLabel;
                      return (
                        <div key={b.id} className="rounded-md overflow-hidden border border-gray-200">
                          <img src={b.image_url} alt={`B${b.blade}`} className="w-full h-12 object-cover bg-gray-100" />
                          <p className={`text-[9px] text-center font-bold uppercase py-0.5 ${LABEL_STYLE[lab].solid}`}>
                            B{b.blade} {lab}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-[10px] text-gray-400 -mt-1">
                    {ins.id} · ถอดที่ {fmt(ins.rul_context?.t_min)} นาที · {ins.status === 'VERIFIED' ? `ยืนยันโดย ${ins.reviewed_by}` : 'ผล AI รอผู้ตรวจยืนยัน'}
                  </p>
                  {ins.status === 'PENDING_REVIEW' ? (
                    <button onClick={() => onOpen(ins.id)} className="btn-primary justify-center">
                      <ClipboardCheck className="w-3.5 h-3.5" /> ไปยืนยันผล AI
                    </button>
                  ) : openRep.length ? (
                    <button onClick={() => onTab('replace')} className="btn-danger justify-center">
                      <Wrench className="w-3.5 h-3.5" /> ใบสั่งงาน: เปลี่ยน {openRep.join(', ')}
                    </button>
                  ) : (
                    <p className="text-[11px] text-emerald-700 font-semibold flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> ใบมีดพร้อม — ติดตั้งดอกกลับเข้าเครื่องได้ (Machine Monitoring)
                    </p>
                  )}
                </>
              )}
              <p className="text-[10px] text-gray-400 mt-auto pt-1 border-t border-gray-50">
                รอยืนยันทั้งหมด {s.pending_review} · ใบมีดค้างเปลี่ยน {s.open_replacements}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ───────────────────────────── รอตรวจสอบ ─────────────────────────────
const ReviewTab: React.FC<{ actor: string; selected: string | null; onSelect: (id: string | null) => void; onDone: () => void; reloadKey: number }> = ({
  actor,
  selected,
  onSelect,
  onDone,
  reloadKey,
}) => {
  const [pending, setPending] = useState<VisionInspection[]>([]);
  const [recent, setRecent] = useState<VisionInspection[]>([]);
  const [ins, setIns] = useState<VisionInspection | null>(null);
  const [labels, setLabels] = useState<Record<number, BladeLabel>>({});
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [zoom, setZoom] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [p, r] = await Promise.all([api.getInspections('PENDING_REVIEW'), api.getInspections('VERIFIED', undefined, 10)]);
    // งานที่ AI ไม่มั่นใจหรือพบใบทื่อ ขึ้นก่อน
    p.sort((a, b) => Number(!!b.low_confidence) - Number(!!a.low_confidence) || Number(b.ai_verdict === 'REPLACE') - Number(a.ai_verdict === 'REPLACE'));
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
      setLabels(Object.fromEntries((d.blades || []).map((b) => [b.blade, (b.final_label || b.pred_label) as BladeLabel])));
      setNote(d.note || '');
    });
  }, [selected]);

  const submit = async () => {
    if (!ins) return;
    setBusy(true);
    setErr(null);
    try {
      await api.reviewInspection(ins.id, actor, Object.entries(labels).map(([k, v]) => ({ blade: Number(k), label: v })), note);
      onSelect(null);
      await load();
      onDone();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const changed = ins?.blades?.filter((b) => labels[b.blade] !== b.pred_label).length ?? 0;
  const readonly = ins?.status === 'VERIFIED';

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
                      ถอดที่ {fmt(p.rul_context?.t_min)} นาที · {fmtDateTime(p.captured_at)}
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
                    {r.machine_id} · {r.tool_ref} · {fmtDateTime(r.reviewed_at)}
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
            <p className="text-sm text-gray-400 py-10 text-center">เลือกรายการทางซ้ายเพื่อยืนยันผล</p>
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
            <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-4 gap-3">
              {ins.blades?.map((b) => {
                const chosen = labels[b.blade];
                const corrected = chosen !== b.pred_label;
                return (
                  <div key={b.id} className={`rounded-xl border overflow-hidden ${corrected ? 'border-amber-300 ring-1 ring-amber-200' : 'border-gray-200'}`}>
                    <button onClick={() => setZoom(b.image_url)} className="block w-full">
                      <img src={b.image_url} alt={`B${b.blade}`} className="w-full h-32 object-cover bg-gray-100 hover:opacity-90" />
                    </button>
                    <div className="p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-sm">ใบมีด B{b.blade}</span>
                        <span className="text-[10px] text-gray-500">AI มั่นใจ {(b.confidence * 100).toFixed(0)}%</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-[11px]">
                        <span className="text-gray-500">AI:</span> <LabelChip label={b.pred_label} />
                      </div>
                      <ProbBars probs={b.probs} />
                      {b.metrology && (
                        <div className="grid grid-cols-3 gap-1 text-center text-[10px] bg-gray-50 rounded-md py-1.5">
                          <div>
                            <p className="text-gray-400">Flank wear</p>
                            <p className="font-semibold tabular-nums">{b.metrology.flank_wear_um.toFixed(0)} µm</p>
                          </div>
                          <div>
                            <p className="text-gray-400">Gaps</p>
                            <p className="font-semibold tabular-nums">{b.metrology.gaps_um.toFixed(0)} µm</p>
                          </div>
                          <div>
                            <p className="text-gray-400">Overhang</p>
                            <p className="font-semibold tabular-nums">{b.metrology.overhang_um.toFixed(0)} µm</p>
                          </div>
                        </div>
                      )}
                      <div>
                        <p className="text-[10px] text-gray-500 mb-1">ผลที่ถูกต้อง (ผู้ตรวจ)</p>
                        <div className="grid grid-cols-3 gap-1">
                          {LABELS.map((l) => (
                            <button
                              key={l}
                              disabled={readonly}
                              onClick={() => setLabels((p) => ({ ...p, [b.blade]: l }))}
                              className={`py-1 rounded-md text-[10px] font-bold uppercase border transition ${
                                chosen === l ? LABEL_STYLE[l].solid + ' shadow-sm' : 'bg-white text-gray-400 border-gray-200 hover:bg-gray-50'
                              } disabled:cursor-default`}
                            >
                              {l}
                            </button>
                          ))}
                        </div>
                        <p className={`text-[10px] mt-1 ${corrected ? 'text-amber-700 font-semibold' : 'text-emerald-700'}`}>
                          {readonly
                            ? b.review === 'CORRECTED'
                              ? `แก้จาก ${b.pred_label} → ${b.final_label}`
                              : 'AI ถูกต้อง'
                            : corrected
                            ? `แก้ AI: ${b.pred_label} → ${chosen} (จะเข้า pool retrain)`
                            : '✓ AI ถูกต้อง'}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            {!readonly ? (
              <div className="mt-4 flex flex-col md:flex-row md:items-center gap-3">
                <input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="หมายเหตุ (ถ้ามี) เช่น พบรอยบิ่นที่ปลายคม"
                  className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-xs"
                />
                <span className="text-xs text-gray-500">
                  AI ถูก {4 - changed}/4 ใบ · ผลรวม <VerdictChip v={(Object.values(labels).includes('dulled') ? 'REPLACE' : Object.values(labels).includes('used') ? 'MONITOR' : 'OK') as ToolVerdict} />
                </span>
                <button onClick={submit} disabled={busy} className="btn-primary">
                  <ClipboardCheck className="w-3.5 h-3.5" /> ยืนยันผล → ออกใบสั่งเปลี่ยนใบมีด
                </button>
              </div>
            ) : (
              <p className="mt-3 text-xs text-gray-500">
                ยืนยันแล้วโดย {ins.reviewed_by} · {fmtDateTime(ins.reviewed_at)} · ผลรวม <VerdictChip v={ins.final_verdict} />
                {ins.note ? ` · ${ins.note}` : ''}
              </p>
            )}
          </Card>
        )}
      </div>
      {zoom && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-6" onClick={() => setZoom(null)}>
          <img src={zoom} alt="zoom" className="max-w-full max-h-full rounded-lg shadow-2xl" />
        </div>
      )}
    </div>
  );
};

// ───────────────────────────── รายงานเปลี่ยนใบมีด ─────────────────────────────
const ReplaceTab: React.FC<{ actor: string; reloadKey: number; onChanged: () => void }> = ({ actor, reloadKey, onChanged }) => {
  const [rep, setRep] = useState<Replacements | null>(null);
  const load = useCallback(() => api.getReplacements().then(setRep), []);
  useEffect(() => {
    load();
  }, [load, reloadKey]);
  const done = async (id: string) => {
    await api.markBladeReplaced(id, actor);
    await load();
    onChanged();
  };
  if (!rep) return <p className="text-sm text-gray-400">กำลังโหลด…</p>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {rep.summary.length === 0 ? (
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-semibold border border-emerald-200">
            <CheckCircle2 className="w-4 h-4" /> ไม่มีใบมีดที่ต้องเปลี่ยน
          </span>
        ) : (
          rep.summary.map((s) => (
            <span
              key={s.inspection_id}
              title={`${s.inspection_id} · ยืนยันโดย ${s.reviewed_by ?? '—'}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-50 text-red-700 text-xs font-semibold border border-red-200"
            >
              <Wrench className="w-4 h-4" /> {s.machine_id} · ดอก {s.tool_ref ?? '—'} (ถอดที่ {fmt(s.removed_t_min)} นาที): เปลี่ยน {s.blades.join(', ')}
            </span>
          ))
        )}
        <a href={api.replacementsCsvUrl()} className="btn-secondary ml-auto">
          <Download className="w-3.5 h-3.5" /> CSV
        </a>
      </div>
      <p className="text-[11px] text-gray-500">
        ใบสั่งงานสำหรับวิศวกร: ใบมีดที่ผู้ตรวจยืนยันว่าทื่อ/เสียของดอกที่ถอดจากเครื่องตามคำแนะนำของแบบจำลอง RUL — เปลี่ยนใบมีดแล้วบันทึก จากนั้นติดตั้งดอกกลับเข้าเครื่องที่ Machine Monitoring
      </p>
      <Card title={`ใบมีดที่ต้องเปลี่ยน (${rep.open.length})`}>
        <ReplaceTable items={rep.open} action={(it) => <button onClick={() => done(it.blade_id)} className="btn-primary">บันทึกว่าเปลี่ยนแล้ว</button>} />
      </Card>
      <Card title={`ประวัติการเปลี่ยน (${rep.done.length})`}>
        <ReplaceTable items={rep.done} action={(it) => <span className="text-[11px] text-gray-500">{it.replaced_by} · {fmtDateTime(it.replaced_at)}</span>} />
      </Card>
    </div>
  );
};

const ReplaceTable: React.FC<{ items: Replacements['open']; action: (it: Replacements['open'][number]) => React.ReactNode }> = ({ items, action }) =>
  items.length === 0 ? (
    <p className="text-xs text-gray-400">—</p>
  ) : (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-gray-500 border-b border-gray-100">
            <th className="py-2 pr-2">ภาพ</th>
            <th className="py-2 pr-2">เครื่อง / ดอก / ใบมีด</th>
            <th className="py-2 pr-2">ถอดตาม RUL</th>
            <th className="py-2 pr-2">รายการตรวจ</th>
            <th className="py-2 pr-2">Flank wear</th>
            <th className="py-2 pr-2">AI ทาย</th>
            <th className="py-2 pr-2">ผลยืนยัน</th>
            <th className="py-2 pr-2">ยืนยันโดย</th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={it.blade_id} className="border-b border-gray-50">
              <td className="py-1.5 pr-2">
                <img src={it.image_url} alt="" className="w-20 h-8 object-cover rounded" />
              </td>
              <td className="py-1.5 pr-2 font-semibold">
                {it.machine_id} · {it.tool_ref ?? '—'} · B{it.blade}
              </td>
              <td className="py-1.5 pr-2 text-gray-500">
                {fmt(it.removed_t_min)} นาที {it.rul_recommendation && <RecBadge rec={it.rul_recommendation} />}
                <br />
                {it.removed_by}
              </td>
              <td className="py-1.5 pr-2 text-gray-500">
                {it.inspection_id}
                <br />
                {fmtDateTime(it.captured_at)}
              </td>
              <td className="py-1.5 pr-2 tabular-nums">{it.flank_wear_um != null ? `${it.flank_wear_um.toFixed(0)} µm` : '—'}</td>
              <td className="py-1.5 pr-2">
                <LabelChip label={it.ai_label} /> {it.ai_correct ? <CheckCircle2 className="inline w-3.5 h-3.5 text-emerald-600" /> : <XCircle className="inline w-3.5 h-3.5 text-red-500" />}
              </td>
              <td className="py-1.5 pr-2">
                <LabelChip label={it.final_label} />
              </td>
              <td className="py-1.5 pr-2 text-gray-500">{it.reviewed_by}</td>
              <td className="py-1.5 text-right">{action(it)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

// ───────────────────────────── โมเดล & retrain ─────────────────────────────
const ModelTab: React.FC<{ actor: string; isAdmin: boolean; reloadKey: number; onChanged: () => void }> = ({ actor, isAdmin, reloadKey, onChanged }) => {
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
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => load().catch(() => {}), 5000);
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

  const m = model?.meta?.metrics;
  return (
    <div className="space-y-4">
      {err && <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{err}</div>}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card
          title={
            <span className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-500" /> แบบจำลองที่ใช้งาน (MinIO)
            </span>
          }
        >
          {!model ? (
            <p className="text-xs text-gray-400">—</p>
          ) : (
            <div className="space-y-1.5 text-xs">
              <p className="text-sm font-bold">{model.version || 'ไม่มี'}</p>
              {model.error && <p className="text-red-600">{model.error}</p>}
              <p className="text-gray-500">{model.meta?.model}</p>
              <p className="text-gray-500">
                ฝึก: ดอก {model.meta?.train_tools?.join(', ')} + label จากคน {model.meta?.n_human_labels ?? 0} ใบ · validation: ดอก {model.meta?.val_tools?.join(', ')}
              </p>
              <div className="grid grid-cols-2 gap-2 pt-1">
                <div className="rounded-lg bg-gray-50 p-2 text-center">
                  <p className="text-[10px] text-gray-500">Validation (ดอก 7)</p>
                  <p className="font-bold">
                    {pct(m?.val?.accuracy)} <span className="text-[10px] font-normal text-gray-400">F1 {m?.val?.macro_f1?.toFixed(2) ?? '—'}</span>
                  </p>
                </div>
                <div className="rounded-lg bg-gray-50 p-2 text-center">
                  <p className="text-[10px] text-gray-500">{m?.held_out ? 'ดอกบนเครื่อง N8–N10' : 'ข้อมูลล่าสุดที่คนยืนยัน'}</p>
                  {(m?.held_out || m?.recent)?.n ? (
                    <p className="font-bold">
                      {pct((m?.held_out || m?.recent)?.accuracy)}{' '}
                      <span className="text-[10px] font-normal text-gray-400">F1 {(m?.held_out || m?.recent)?.macro_f1?.toFixed(2) ?? '—'}</span>
                    </p>
                  ) : (
                    <p className="text-[11px] text-gray-400 mt-1">ยังไม่พอประเมิน (ต้องมี label ≥ 10 ใบ)</p>
                  )}
                </div>
              </div>
              <p className="text-[10px] text-gray-400">sha256 {model.sha256?.slice(0, 16)}… · โหลด {fmtDateTime(model.loaded_at)}</p>
            </div>
          )}
        </Card>
        <Card
          title={
            <span className="flex items-center gap-2">
              <ScanEye className="w-4 h-4 text-indigo-500" /> AI เทียบผลที่คนยืนยัน
            </span>
          }
        >
          {!stats || stats.reviewed_blades === 0 ? (
            <p className="text-xs text-gray-400">ยังไม่มีผลที่ยืนยัน</p>
          ) : (
            <div className="text-xs space-y-2">
              <p>
                AI ตรงกับผู้ตรวจ <b className="text-lg">{stats.agreement_pct}%</b> จาก {stats.reviewed_blades} ใบ (แก้ {stats.corrected} ใบ)
              </p>
              <table className="w-full text-center">
                <thead>
                  <tr className="text-[10px] text-gray-500">
                    <th className="text-left">คน \ AI</th>
                    {LABELS.map((l) => (
                      <th key={l} className="uppercase">
                        {l}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {LABELS.map((t) => (
                    <tr key={t}>
                      <td className="text-left uppercase text-[10px] text-gray-500">{t}</td>
                      {LABELS.map((p) => (
                        <td key={p} className={`py-1 tabular-nums ${t === p ? 'font-bold text-emerald-700 bg-emerald-50' : stats.confusion_human_vs_ai[t][p] ? 'text-red-600' : 'text-gray-300'}`}>
                          {stats.confusion_human_vs_ai[t][p]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
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
                label ใหม่ที่ยังไม่เคยใช้ฝึก <b>{pool.n_labels}</b> ใบ · AI ผิดแล้วคนแก้ <b className="text-amber-700">{pool.n_corrected}</b> · AI ถูก {pool.n_confirmed}
              </p>
              <div className="h-2 rounded bg-gray-100 overflow-hidden">
                <div className="h-full bg-amber-500" style={{ width: `${Math.min(100, (pool.n_corrected / pool.threshold) * 100)}%` }} />
              </div>
              <p className="text-[11px] text-gray-500">
                {pool.suggest_retrain ? 'แนะนำให้ retrain แล้ว' : `แนะนำ retrain เมื่อมีกรณีที่ AI ผิด ≥ ${pool.threshold} ใบ`}
              </p>
              <button
                disabled={!isAdmin || busy || running || pool.n_labels === 0}
                onClick={() => act(() => api.startRetrain(actor))}
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

      <Card title="งาน retrain และ candidate model">
        {jobs.length === 0 ? (
          <p className="text-xs text-gray-400">ยังไม่มีงาน retrain</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-gray-500 border-b border-gray-100">
                  <th className="py-2 pr-2">งาน</th>
                  <th className="py-2 pr-2">สถานะ</th>
                  <th className="py-2 pr-2">label (แก้)</th>
                  <th className="py-2 pr-2">Validation ดอก 7: เดิม → ใหม่</th>
                  <th className="py-2 pr-2">ข้อมูลล่าสุดที่คนยืนยัน: เดิม → ใหม่</th>
                  <th className="py-2 pr-2">Gate</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => {
                  const r = j.result;
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
                        {j.error && <p className="text-[10px] text-red-600 max-w-xs">{j.error}</p>}
                      </td>
                      <td className="py-2 pr-2 tabular-nums">
                        {j.n_labels} ({j.n_corrected})
                      </td>
                      <td className="py-2 pr-2 tabular-nums">
                        {r ? `${pct(r.metrics.base_val.accuracy)} → ${pct(r.metrics.val.accuracy)} (F1 ${r.metrics.base_val.macro_f1?.toFixed(2)} → ${r.metrics.val.macro_f1?.toFixed(2)})` : '—'}
                      </td>
                      <td className="py-2 pr-2 tabular-nums">
                        {r && r.n_recent_eval ? `${pct(r.metrics.base_recent.accuracy)} → ${pct(r.metrics.recent.accuracy)} (${r.n_recent_eval} ใบ)` : r ? 'ข้อมูลยังน้อย' : '—'}
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
                            <button disabled={busy || !r?.gate.passed} onClick={() => act(() => api.decideTrainingJob(j.id, 'promote', actor))} className="btn-primary" title={r?.gate.passed ? '' : 'ไม่ผ่าน gate'}>
                              Promote
                            </button>
                            <button disabled={busy} onClick={() => act(() => api.decideTrainingJob(j.id, 'reject', actor))} className="btn-secondary">
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
              Gate: macro-F1 บน validation (ดอก 7) ลดไม่เกิน 0.02 และ accuracy บนข้อมูลล่าสุดที่คนยืนยัน (20% ท้าย ไม่ใช้ฝึก) ต้องไม่ลดลง — candidate จะถูกใช้งานเมื่อผู้ดูแลกด Promote เท่านั้น
            </p>
          </div>
        )}
      </Card>

      <Card title="เวอร์ชันใน MinIO (models/tool-vision/)">
        <ul className="text-xs space-y-1">
          {versions.map((v) => (
            <li key={v.version} className="flex items-center gap-2">
              <span className="font-mono">{v.version}</span>
              {v.active && <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 text-[10px]">ใช้งาน</span>}
              <span className="text-gray-400">
                {v.status} · {fmtDateTime(v.created_utc)} · label จากคน {v.n_human_labels ?? 0}
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
  const actor = user?.name || 'operator';
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
        { id: 'replace', label: `ใบสั่งเปลี่ยนใบมีด${counts.replace ? ` (${counts.replace})` : ''}`, icon: Wrench },
        { id: 'model', label: 'โมเดล & Retrain', icon: RefreshCw },
      ] as const,
    [counts],
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Tool Inspection (Vision)"
        subtitle="ต่อจาก Machine Monitoring: ดอกที่ RUL แจ้งหมดอายุและถูกถอด → ภาพ 4 ใบมีด → AI ชี้ใบที่เสีย → ผู้ตรวจยืนยัน → ใบสั่งเปลี่ยนใบมีดให้วิศวกร"
        actions={
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
              model?.status === 'READY' ? 'bg-indigo-50 text-indigo-700 border-indigo-200' : 'bg-red-50 text-red-700 border-red-200'
            }`}
            title={model?.error || ''}
          >
            <ShieldAlert className="w-3.5 h-3.5" /> {model?.status === 'READY' ? `MinIO · ${model.version}` : 'Vision model unavailable'}
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
          actor={actor}
          reloadKey={reloadKey}
          onTab={(t) => setParams({ tab: t })}
          onOpen={(id) => {
            setSelected(id);
            setParams({ tab: 'review', inspection: id });
            refreshCounts();
          }}
        />
      )}
      {tab === 'review' && <ReviewTab actor={actor} selected={selected} onSelect={setSelected} onDone={bump} reloadKey={reloadKey} />}
      {tab === 'replace' && <ReplaceTab actor={actor} reloadKey={reloadKey} onChanged={bump} />}
      {tab === 'model' && <ModelTab actor={actor} isAdmin={isAdmin} reloadKey={reloadKey} onChanged={bump} />}
    </div>
  );
};

export default ToolVisionPage;
