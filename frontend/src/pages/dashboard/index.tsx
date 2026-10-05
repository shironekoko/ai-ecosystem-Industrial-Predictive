import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Area, AreaChart, ResponsiveContainer, YAxis } from 'recharts';
import {
  AlarmClock,
  BellRing,
  Database,
  Gauge,
  Layers,
  ShieldCheck,
  Timer,
  Wrench,
} from 'lucide-react';
import { PageHeader, StatCard } from '../../components/common';
import {
  Card,
  ConnBadge,
  MACHINE_COLOR,
  PHASE_TEXT,
  RecBadge,
  StreamBadge,
  WearBadge,
  fmt,
  fmtClock,
} from '../../components/toollife/ui';
import { useFleet, useMachineHistory } from '../../hooks/useToolLife';
import { api } from '../../services/api';
import type { MachineSnapshot, StreamEvent, ToolLifeSummary, VisionStation } from '../../types';

const LAYER_MIN = 164 / 60;

const LifeBar: React.FC<{ m: MachineSnapshot }> = ({ m }) => {
  const p = m.prediction;
  if (!p || m.t_min === null) return <div className="h-2.5 rounded-full bg-gray-100" />;
  const total = m.t_min + p.rul_min;
  const used = Math.min(100, (m.t_min / total) * 100);
  const accelAt = Math.min(100, ((m.t_min + p.rul_accel_min) / total) * 100);
  return (
    <div className="relative h-2.5 rounded-full bg-gray-100 overflow-hidden" title="สัดส่วนอายุที่ใช้ไปแล้ว (ประมาณจากแบบจำลอง)">
      <div className="absolute inset-y-0 left-0 bg-emerald-100" style={{ width: `${accelAt}%` }} />
      <div className="absolute inset-y-0 bg-amber-100" style={{ left: `${accelAt}%`, right: 0 }} />
      <div
        className="absolute inset-y-0 left-0 rounded-full"
        style={{ width: `${used}%`, background: p.wear_state === 'STEADY' ? '#10b981' : p.wear_state === 'ACCELERATED' ? '#f59e0b' : '#ef4444' }}
      />
    </div>
  );
};

const MachineCard: React.FC<{ m: MachineSnapshot }> = ({ m }) => {
  const { history } = useMachineHistory(m.machine);
  const spark = useMemo(
    () => history.filter((h) => h.rul !== null).map((h) => ({ t: h.t_min, rul: h.rul as number, lo: h.rul_lo, hi: h.rul_hi })),
    [history],
  );
  const p = m.prediction;
  return (
    <div className={`bg-white rounded-xl border shadow-sm flex flex-col ${p?.recommendation === 'REPLACE_NOW' ? 'border-red-300 ring-2 ring-red-100' : 'border-gray-200'}`}>
      <div className="px-4 pt-4 flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: MACHINE_COLOR[m.machine] }} />
            <span className="font-bold text-gray-900">{m.machine_id}</span>
            <span className="text-xs text-gray-400">ดอก {m.tool_id}</span>
          </div>
          <p className="text-[11px] text-gray-400 mt-0.5">{m.feed_drive}</p>
        </div>
        <StreamBadge state={m.state} speed={m.speed} />
      </div>

      <div className="px-4 pt-3">
        {p ? (
          <>
            <div className="flex items-end justify-between">
              <div>
                <p className="text-[11px] font-medium text-gray-500">อายุใช้งานที่เหลือ (RUL)</p>
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-bold text-gray-900 tabular-nums">{fmt(p.rul_min)}</span>
                  <span className="text-sm text-gray-400">นาทีของเวลาตัด</span>
                </div>
                <p className="text-[11px] text-gray-500 tabular-nums">
                  ช่วง P10–P90: {fmt(p.rul_lo)} – {fmt(p.rul_hi)} นาที · ≈ {fmt(p.rul_min / LAYER_MIN, 1)} ชั้นงาน
                </p>
              </div>
              <div className="flex flex-col items-end gap-1">
                <RecBadge rec={p.recommendation} size="md" />
                <WearBadge state={p.wear_state} />
              </div>
            </div>
            <div className="mt-3">
              <LifeBar m={m} />
              <div className="flex justify-between text-[10px] text-gray-400 mt-1">
                <span>ใช้ไป {fmt(p.life_used_pct, 0)}%</span>
                <span>สึกเร่งในอีก {fmt(p.rul_accel_min)} นาที</span>
              </div>
            </div>
          </>
        ) : (
          <div className="py-3">
            <p className="text-sm font-medium text-gray-600">{m.model_ready ? PHASE_TEXT[m.phase] : 'แบบจำลองยังไม่พร้อม (MinIO)'}</p>
            {m.phase === 'BASELINE' && (
              <div className="mt-2">
                <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
                  <div className="h-full bg-indigo-400" style={{ width: `${((m.baseline_runs || 0) / 29) * 100}%` }} />
                </div>
                <p className="text-[11px] text-gray-400 mt-1">{m.baseline_runs || 0}/29 รันหลัง break-in</p>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="h-16 px-1 mt-2">
        {spark.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={spark} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
              <YAxis hide domain={[0, 'auto']} />
              <Area type="monotone" dataKey="rul" stroke={MACHINE_COLOR[m.machine]} fill={MACHINE_COLOR[m.machine]} fillOpacity={0.12} strokeWidth={1.8} isAnimationActive={false} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-[11px] text-gray-300">แนวโน้ม RUL จะปรากฏเมื่อเริ่มพยากรณ์</div>
        )}
      </div>

      <div className="grid grid-cols-3 border-t border-gray-100 text-center text-[11px] mt-auto">
        <div className="py-2">
          <p className="text-gray-400">เวลาตัดสะสม</p>
          <p className="font-semibold text-gray-700 tabular-nums">{fmt(m.t_min)} นาที</p>
        </div>
        <div className="py-2 border-x border-gray-100">
          <p className="text-gray-400">รันที่</p>
          <p className="font-semibold text-gray-700 tabular-nums">
            {m.run_index}/{m.n_runs}
          </p>
        </div>
        <div className="py-2">
          <p className="text-gray-400">ครบกำหนด (ETA)</p>
          <p className="font-semibold text-gray-700 tabular-nums">{fmtClock(p?.eta_utc)}</p>
        </div>
      </div>
      <Link
        to={`/machine-monitoring?machine=${m.machine}`}
        className="text-center text-xs font-semibold text-indigo-600 hover:bg-indigo-50 py-2 border-t border-gray-100 rounded-b-xl"
      >
        เปิดหน้าติดตามเครื่อง →
      </Link>
    </div>
  );
};

/** ไอเดีย: วางแผนเปลี่ยนดอกพร้อมกันหลายเครื่อง — แสดงช่วงเวลาที่แต่ละดอกน่าจะครบอายุบนแกนเวลาเดียวกัน */
const ReplacementPlanner: React.FC<{ machines: MachineSnapshot[] }> = ({ machines }) => {
  const rows = machines.filter((m) => m.prediction && m.state !== 'COMPLETED');
  const k = (m: MachineSnapshot) => (m.prediction?.wall_s_per_cut_min ?? 60 / (m.speed || 1)) / 60; // นาทีนาฬิกาต่อนาทีตัด
  const horizon = Math.max(30, ...rows.map((m) => (m.prediction!.rul_hi || 0) * k(m)));
  const scale = (min: number) => `${Math.min(100, (min / horizon) * 100)}%`;
  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          <AlarmClock className="w-4 h-4 text-indigo-500" /> แผนเปลี่ยนดอก (Replacement planner)
        </span>
      }
      right={<span className="text-[11px] text-gray-400">แกนเวลา = นาทีนาฬิกาจากตอนนี้ (แปลงจากเวลาตัดด้วยอัตราที่วัดได้จริงของแต่ละเครื่อง)</span>}
    >
      {rows.length === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">ยังไม่มีเครื่องที่มีผลพยากรณ์</p>
      ) : (
        <div className="space-y-3">
          {rows.map((m) => {
            const p = m.prediction!;
            const s = 1 / k(m);
            return (
              <div key={m.machine} className="flex items-center gap-3">
                <div className="w-20 text-xs font-semibold text-gray-700">
                  {m.machine_id} · {m.tool_id}
                </div>
                <div className="relative flex-1 h-6 bg-gray-50 rounded">
                  <div className="absolute inset-y-1 rounded bg-indigo-100" style={{ left: scale(p.rul_lo / s), width: `calc(${scale(p.rul_hi / s)} - ${scale(p.rul_lo / s)})` }} />
                  <div className="absolute inset-y-0 w-0.5 bg-indigo-600" style={{ left: scale(p.rul_min / s) }} />
                  <div className="absolute inset-y-0 border-l border-dashed border-red-300" style={{ left: scale(LAYER_MIN / s) }} title="1 ชั้นงาน" />
                </div>
                <div className="w-36 text-right text-[11px] text-gray-600 tabular-nums">
                  {fmt(p.rul_lo / s, 0)}–{fmt(p.rul_hi / s, 0)} นาที · {fmtClock(p.eta_utc)}
                </div>
              </div>
            );
          })}
          <div className="flex justify-between text-[10px] text-gray-400 pl-[92px] pr-[156px]">
            <span>ตอนนี้</span>
            <span>+{Math.round(horizon / 2)} นาที</span>
            <span>+{Math.round(horizon)} นาที</span>
          </div>
          <p className="text-[11px] text-gray-500">
            แถบ = ช่วง P10–P90 ของเวลาที่ดอกจะถึงเกณฑ์ VB 140 µm, เส้นเข้ม = ค่าพยากรณ์; ถ้าหลายแถบซ้อนกันสามารถรวบการเปลี่ยนดอกในจังหวะหยุดเครื่องเดียว
          </p>
        </div>
      )}
    </Card>
  );
};

const levelCls = { INFO: 'bg-sky-50 text-sky-700', WARNING: 'bg-amber-50 text-amber-700', CRITICAL: 'bg-red-50 text-red-700' };

export const DashboardPage: React.FC = () => {
  const { fleet, conn, events, error } = useFleet();
  const [summary, setSummary] = useState<ToolLifeSummary | null>(null);
  const [unread, setUnread] = useState<number>(0);
  const [vision, setVision] = useState<VisionStation[] | null>(null);

  useEffect(() => {
    const load = () => {
      api.getToolLifeSummary().then(setSummary).catch(() => setSummary(null));
      api.getAlarms('ALL', false).then((a: any[]) => setUnread(Array.isArray(a) ? a.length : 0));
      api.getVisionStations().then(setVision).catch(() => setVision(null));
    };
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  const machines = fleet?.machines ?? [];
  const predicted = machines.filter((m) => m.prediction && m.state !== 'COMPLETED');
  const lowest = predicted.reduce<MachineSnapshot | null>((a, m) => (!a || m.prediction!.rul_min < a.prediction!.rul_min ? m : a), null);
  const cutting = machines.filter((m) => m.state === 'CUTTING').length;
  const mergedEvents: StreamEvent[] = useMemo(() => {
    const all = [...events, ...machines.flatMap((m) => m.events)];
    const seen = new Set<string>();
    return all
      .filter((e) => {
        const k = `${e.at}|${e.message}`;
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
      })
      .sort((a, b) => (a.at < b.at ? 1 : -1))
      .slice(0, 12);
  }, [events, machines]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tool Life Dashboard"
        subtitle="อายุใช้งานที่เหลือของดอกกัดจากแบบจำลองอนุกรมเวลา (GRU) — ข้อมูลจริงจากชุดข้อมูล LUH ของดอกที่ไม่ได้ใช้ฝึก ไหลตามเวลาจริง"
        actions={
          <>
            <ConnBadge conn={conn} />
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                fleet?.model.status === 'READY' ? 'bg-indigo-50 text-indigo-700 border-indigo-200' : 'bg-red-50 text-red-700 border-red-200'
              }`}
              title={fleet?.model.error || ''}
            >
              <Database className="w-3.5 h-3.5" />
              {fleet?.model.status === 'READY' ? `MinIO · ${fleet.model.version}` : 'Model unavailable'}
            </span>
          </>
        }
      />

      {(error || fleet?.error) && (
        <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{fleet?.error || `เชื่อมต่อ backend ไม่ได้: ${error}`}</div>
      )}
      {fleet && fleet.model.status !== 'READY' && (
        <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800">
          แบบจำลองยังไม่ถูกโหลดจาก MinIO ({fleet.model.error || fleet.model.status}) — สตรีมข้อมูลยังทำงาน แต่จะไม่มีการพยากรณ์จนกว่าจะอัปโหลดแบบจำลอง
          (<code className="text-xs">uv run python scripts/publish_tool_rul_model.py</code>)
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label="เครื่องที่กำลังตัด" value={`${cutting}/${machines.length || 0}`} icon={Gauge} accent="emerald" trendLabel="สตรีมดอกที่สงวนไว้ (ไม่ได้ใช้ฝึก)" />
        <StatCard
          label="RUL ต่ำสุดในกอง"
          value={lowest ? fmt(lowest.prediction!.rul_min) : '—'}
          unit={lowest ? `นาที · ${lowest.machine_id}` : undefined}
          icon={Timer}
          accent={lowest?.prediction?.recommendation === 'REPLACE_NOW' ? 'red' : 'amber'}
          trendLabel={lowest ? `P10 ${fmt(lowest.prediction!.rul_lo)} นาที` : 'รอผลพยากรณ์'}
        />
        <StatCard
          label="เปลี่ยนดอกครั้งถัดไป"
          value={lowest ? fmtClock(lowest.prediction!.eta_utc) : '—'}
          icon={Wrench}
          accent="indigo"
          trendLabel={lowest ? `${lowest.machine_id}/${lowest.tool_id}` : '—'}
        />
        <StatCard label="การแจ้งเตือนที่ยังไม่อ่าน" value={unread} icon={BellRing} accent={unread ? 'red' : 'blue'} trendLabel="จากผลพยากรณ์จริงเท่านั้น" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {machines.map((m) => (
          <MachineCard key={m.machine} m={m} />
        ))}
        {!fleet && <div className="lg:col-span-3 text-center text-sm text-gray-400 py-12">กำลังโหลดสถานะเครื่อง…</div>}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2">
          <ReplacementPlanner machines={machines} />
        </div>
        <Card
          title={
            <span className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-indigo-500" /> สุขภาพข้อมูลและแบบจำลอง
            </span>
          }
        >
          <div className="space-y-2.5 text-xs">
            {machines.map((m) => (
              <div key={m.machine} className="flex items-center justify-between">
                <span className="font-medium text-gray-700">
                  {m.machine_id}/{m.tool_id}
                </span>
                <span className="flex items-center gap-3 text-gray-500 tabular-nums">
                  <span title="ค่า |z| สูงสุดของอินพุตเซนเซอร์เทียบช่วงข้อมูลฝึก — เกิน 4 = นอกช่วงที่แบบจำลองเคยเห็น">
                    drift |z|max{' '}
                    <b className={m.input_z_max !== null && m.input_z_max > 4 ? 'text-red-600' : 'text-gray-700'}>{fmt(m.input_z_max, 2)}</b>
                  </span>
                  <span title="จำนวนรันที่ตัวกรอง causal ตรวจพบค่าผิดปกติชั่วขณะ">
                    spikes <b className="text-gray-700">{m.flagged_runs}</b>
                  </span>
                </span>
              </div>
            ))}
            <div className="pt-2 border-t border-gray-100 text-[11px] text-gray-500 leading-relaxed">
              อินพุตของแบบจำลอง: เวลาตัดสะสม, เครื่อง, ตำแหน่งแนวตัด และค่าเฉลี่ยรายรันของแรงบิด spindle, แรง/แรงบิดมอเตอร์แกน X/Y และแรงตัด Fx/Fy/Fz/Fres —
              <b> ไม่มี VB</b> (VB ใช้เป็น label ตอนฝึกเท่านั้น)
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2">
          <Card
            title={
              <span className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-500" /> เหตุการณ์ล่าสุด
              </span>
            }
          >
            {mergedEvents.length === 0 ? (
              <p className="text-sm text-gray-400 py-4 text-center">ยังไม่มีเหตุการณ์</p>
            ) : (
              <ul className="divide-y divide-gray-100">
                {mergedEvents.map((e, i) => (
                  <li key={i} className="py-2 flex items-start gap-3 text-xs">
                    <span className="text-gray-400 tabular-nums w-16 shrink-0">{fmtClock(e.at)}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold shrink-0 ${levelCls[e.level]}`}>{e.level}</span>
                    {e.machine && <span className="font-semibold text-gray-600 shrink-0">M{e.machine}</span>}
                    <span className="text-gray-700">{e.message}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
        <div className="space-y-4">
          <Card title="ดอกที่ถอดแล้ว (ประเมินเทียบ VB จริง)" right={<Link to="/reports" className="text-xs text-indigo-600 font-semibold">ดูรายงาน →</Link>}>
            {!summary || summary.completedTools === 0 ? (
              <p className="text-xs text-gray-400 leading-relaxed">
                ยังไม่มีดอกที่ถอดออก — ค่า VB จริงจะเปิดเผยหลังดอกถูกถอดและวัดเท่านั้น (ระหว่างใช้งานหน้าเว็บไม่แสดงค่าจริง)
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-3 text-center">
                <div className="p-2 rounded-lg bg-gray-50">
                  <p className="text-[11px] text-gray-500">ดอกที่ประเมินแล้ว</p>
                  <p className="text-lg font-bold">{summary.completedTools}</p>
                </div>
                <div className="p-2 rounded-lg bg-gray-50">
                  <p className="text-[11px] text-gray-500">เปลี่ยนช้าเกินเกณฑ์</p>
                  <p className={`text-lg font-bold ${summary.lateReplacements ? 'text-red-600' : 'text-emerald-600'}`}>{summary.lateReplacements}</p>
                </div>
                <div className="p-2 rounded-lg bg-gray-50">
                  <p className="text-[11px] text-gray-500">MAE ของ RUL</p>
                  <p className="text-lg font-bold">{fmt(summary.meanAbsRulErrorMin, 2)} นาที</p>
                </div>
                <div className="p-2 rounded-lg bg-gray-50">
                  <p className="text-[11px] text-gray-500">ใช้อายุดอกได้</p>
                  <p className="text-lg font-bold">{fmt(summary.meanLifeUsedAtReplacePct, 0)}%</p>
                </div>
              </div>
            )}
          </Card>
          <Card title="ตรวจใบมีดของดอกที่ถอด (4 ใบ/ดอก)" right={<Link to="/tool-vision" className="text-xs text-indigo-600 font-semibold">เปิดหน้าตรวจ →</Link>}>
            {!vision ? (
              <p className="text-xs text-gray-400">เชื่อมต่อบริการตรวจภาพไม่ได้</p>
            ) : (
              <ul className="space-y-2 text-xs">
                {vision.map((v) => (
                  <li key={v.machine} className="flex items-center justify-between">
                    <span className="font-semibold text-gray-700">
                      {v.machine_id}{' '}
                      <span className="font-normal text-gray-400">
                        · ดอก {v.tool_id ?? '—'} ·{' '}
                        {v.cycle_inspection
                          ? v.cycle_inspection.status === 'VERIFIED'
                            ? 'ตรวจแล้ว'
                            : 'ถอดแล้ว รอตรวจ'
                          : v.rul?.state === 'COMPLETED'
                          ? 'ถอดแล้ว'
                          : 'อยู่บนเครื่อง'}
                      </span>
                    </span>
                    <span className="flex items-center gap-2">
                      {v.pending_review > 0 && (
                        <Link to="/tool-vision?tab=review" className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 font-semibold">
                          รอยืนยัน {v.pending_review}
                        </Link>
                      )}
                      {v.open_replacements > 0 ? (
                        <Link to="/tool-vision?tab=replace" className="px-1.5 py-0.5 rounded bg-red-50 text-red-700 border border-red-200 font-semibold">
                          ใบสั่งงาน {v.open_replacements}
                        </Link>
                      ) : (
                        <span className="text-emerald-600">ใบมีดปกติ</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
