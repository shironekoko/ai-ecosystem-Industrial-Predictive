/**
 * Model Registry — แบบจำลองวัดรอยสึก VB จากภาพใบมีด (MinIO prefix "tool-vision/")
 * แบบจำลองที่ใช้งาน · ผลประเมิน · กราฟการเทรนรายเวอร์ชัน · งาน retrain (กราฟสด) · สลับเวอร์ชัน
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, ExternalLink, LineChart as LineIcon, RefreshCw, ScanEye, XCircle } from 'lucide-react';
import { TrainingCurves } from '../../components/toollife/TrainingCurves';
import { Card, fmt, fmtDateTime } from '../../components/toollife/ui';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import type { TrainingJob, VisionModelInfo, VisionVersion } from '../../types';

const Row: React.FC<{ k: string; v: React.ReactNode }> = ({ k, v }) => (
  <div className="flex justify-between gap-3">
    <span className="text-gray-500 shrink-0">{k}</span>
    <span className="text-gray-800 text-right">{v}</span>
  </div>
);

export const VERSION_STATUS: Record<string, { label: string; cls: string }> = {
  production: { label: 'ใช้งาน', cls: 'bg-emerald-100 text-emerald-700' },
  previous: { label: 'เวอร์ชันก่อน', cls: 'bg-gray-100 text-gray-600' },
  candidate: { label: 'candidate รอตัดสิน', cls: 'bg-amber-100 text-amber-700' },
};
const tensorboardUrl = () => `${window.location.protocol}//${window.location.hostname}:6006`;

const MetricRow: React.FC<{ label: string; m?: any; note?: string }> = ({ label, m, note }) => (
  <tr className="border-b border-gray-50">
    <td className="py-1.5 pr-2">
      {label}
      {note && <span className="block text-[10px] text-gray-400">{note}</span>}
    </td>
    <td className="py-1.5 px-2 text-right tabular-nums">{m?.n ?? '—'}</td>
    <td className="py-1.5 px-2 text-right tabular-nums font-semibold">{fmt(m?.mae, 1)}</td>
    <td className="py-1.5 px-2 text-right tabular-nums">{fmt(m?.mae_ge103, 1)}</td>
    <td className="py-1.5 px-2 text-right tabular-nums">{m?.zone_acc != null ? `${m.zone_acc.toFixed(0)}%` : '—'}</td>
    <td className="py-1.5 px-2 text-right tabular-nums">{m?.eol_recall != null ? `${m.eol_recall.toFixed(0)}%` : '—'}</td>
  </tr>
);

export const VisionRegistry: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [info, setInfo] = useState<VisionModelInfo | null>(null);
  const [versions, setVersions] = useState<VisionVersion[]>([]);
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [sel, setSel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [m, v, j] = await Promise.all([
      api.getVisionModel(),
      api.getVisionVersions().catch(() => [] as VisionVersion[]),
      api.getTrainingJobs().catch(() => [] as TrainingJob[]),
    ]);
    setInfo(m);
    setVersions(v);
    setJobs(j);
  }, []);
  useEffect(() => {
    load().catch((e) => setErr(e.message));
  }, [load]);

  const running = jobs.some((j) => j.status === 'QUEUED' || j.status === 'RUNNING');
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => api.getTrainingJobs().then(setJobs).catch(() => {}), 3000);   // กราฟสดระหว่าง retrain
    return () => clearInterval(t);
  }, [running]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      await load();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const shown = useMemo(() => versions.find((v) => v.version === (sel ?? info?.version)) ?? versions[0], [versions, sel, info]);
  const meta = info?.meta;
  const mt = meta?.metrics;
  const tl = mt?.tool_level;

  return (
    <div className="space-y-4">
      {err && <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{err}</div>}
      <div className="flex flex-wrap justify-end gap-2">
        <a href={tensorboardUrl()} target="_blank" rel="noreferrer" className="btn-secondary">
          <ExternalLink className="w-3.5 h-3.5" /> เปิด TensorBoard
        </a>
        <button
          onClick={() => act(() => api.reloadVisionModel())}
          disabled={busy || !isAdmin}
          title={isAdmin ? '' : 'เฉพาะผู้ดูแลระบบ'}
          className="btn-primary"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${busy ? 'animate-spin' : ''}`} /> ดึงเวอร์ชันล่าสุดจาก MinIO
        </button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card
          title={
            <span className="flex items-center gap-2">
              <ScanEye className="w-4 h-4 text-indigo-500" /> แบบจำลองที่ใช้งานอยู่
            </span>
          }
        >
          {!info ? (
            <p className="text-sm text-gray-400">เชื่อมต่อ backend ไม่ได้</p>
          ) : (
            <div className="space-y-2 text-xs">
              <div className="flex items-center gap-2">
                {info.status === 'READY' ? <CheckCircle2 className="w-5 h-5 text-emerald-600" /> : <XCircle className="w-5 h-5 text-red-600" />}
                <span className="text-sm font-bold break-all">{info.status === 'READY' ? info.version : 'ไม่มีแบบจำลอง'}</span>
              </div>
              {info.error && <p className="text-red-600 break-all">{info.error}</p>}
              {meta && (
                <>
                  <Row k="งาน" v="regression: ภาพ 1 ใบ → VB (µm)" />
                  <Row
                    k="สถาปัตยกรรม"
                    v={
                      (meta.ensemble ?? 1) > 1
                        ? `${meta.arch} + หัว regression × ${meta.ensemble} ตัว (เฉลี่ยค่า VB) · ${(meta.n_params / meta.ensemble / 1e6).toFixed(2)}M params/ตัว`
                        : `${meta.model} · ${(meta.n_params / 1e6).toFixed(2)}M params`
                    }
                  />
                  <Row k="อินพุต" v={`${meta.image_size?.join('×')} px (คงสัดส่วนภาพ)`} />
                  {meta.config && (
                    <Row
                      k="การฝึก"
                      v={`${meta.config.epochs} epoch · augmentation ${meta.config.aug === 'strong' ? 'สี/แสงแรง' : 'พื้นฐาน'}${meta.config.ema_decay ? ' · EMA' : ''}`}
                    />
                  )}
                  <Row k="ฝึก / val / test" v={`ดอก ${meta.train_tools?.join(',')} / ${meta.val_tools?.join(',')} / ${meta.test_tools?.join(',')}`} />
                  <Row k="ค่าวัดจากคน (retrain)" v={`${meta.n_human_labels ?? 0} ใบ`} />
                  <Row k="เกณฑ์" v={`ใกล้หมดอายุ ${meta.thresholds?.vb_accel_um} µm · หมดอายุ ${meta.thresholds?.vb_eol_um} µm (เฉลี่ย 4 ใบ)`} />
                  {meta.interval && <Row k="P10–P90 รายใบ" v={`${meta.interval.q_lo} / +${meta.interval.q_hi} µm`} />}
                  {meta.interval_tool && <Row k="P10–P90 ค่าเฉลี่ยดอก" v={`${meta.interval_tool.q_lo} / +${meta.interval_tool.q_hi} µm`} />}
                  <Row k="CPU" v={`${meta.cpu_latency_ms_per_image} ms/ภาพ`} />
                  <Row k="sha256" v={<span className="font-mono">{info.sha256?.slice(0, 16)}…</span>} />
                  <Row k="โหลดเมื่อ" v={fmtDateTime(info.loaded_at)} />
                  <Row k="self-test" v={info.status === 'READY' ? 'ผ่าน' : '—'} />
                </>
              )}
            </div>
          )}
        </Card>

        <Card title="ผลประเมิน (หน่วย µm)" className="xl:col-span-2">
          {!mt ? (
            <p className="text-sm text-gray-400">—</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-100">
                    <th className="py-2 pr-2">ชุดข้อมูล</th>
                    <th className="py-2 px-2 text-right">n</th>
                    <th className="py-2 px-2 text-right">MAE</th>
                    <th className="py-2 px-2 text-right">MAE (VB ≥ 103)</th>
                    <th className="py-2 px-2 text-right">โซนถูก</th>
                    <th className="py-2 px-2 text-right">recall หมดอายุ</th>
                  </tr>
                </thead>
                <tbody>
                  <MetricRow label="Cross-validation ดอก 1–7 (รายใบ)" m={meta?.cv} note="leave-one-tool-out" />
                  {tl?.cv && <MetricRow label="Cross-validation ระดับดอก (เฉลี่ย 4 ใบ)" m={tl.cv} />}
                  <MetricRow label="Validation ดอก 7" m={mt.val} note="ใช้เป็น gate ของ retrain" />
                  {mt.test && <MetricRow label="Test ดอก 8–10 (รายใบ)" m={mt.test} note="ดอกบนเครื่อง M1–M3 — ไม่เคยใช้ฝึก/เลือก" />}
                  {tl?.test && <MetricRow label="Test ระดับดอก (เฉลี่ย 4 ใบ)" m={tl.test} />}
                  {mt.test_eol_runs && <MetricRow label="Test เฉพาะภาพตอนถอดดอก" m={mt.test_eol_runs} />}
                  {mt.recent && <MetricRow label="ค่าที่คนวัดล่าสุด (ไม่ใช้ฝึก)" m={mt.recent} note="ผลของ retrain" />}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <Card
        title={
          <span className="flex items-center gap-2">
            <LineIcon className="w-4 h-4 text-indigo-500" /> กราฟการเทรน
          </span>
        }
        right={
          versions.length > 0 && (
            <select value={shown?.version ?? ''} onChange={(e) => setSel(e.target.value)} className="border border-gray-200 rounded-md px-2 py-1 text-xs bg-white">
              {versions.map((v) => (
                <option key={v.version} value={v.version}>
                  {v.version}
                  {v.active ? ' (ใช้งาน)' : ''}
                </option>
              ))}
            </select>
          )
        }
      >
        {shown?.history?.length ? (
          <>
            <TrainingCurves history={shown.history} epochs={shown.epochs ?? undefined} />
            <p className="text-[10px] text-gray-400 mt-2">
              {shown.base_version ? `fine-tune จาก ${shown.base_version} ด้วยค่าวัดจากคน ${shown.n_human_labels ?? 0} ใบ · ` : 'ฝึกบนดอก 1–6 · '}
              validation = ดอก 7 · ใช้น้ำหนักของ epoch สุดท้าย (จำนวน epoch เลือกด้วย cross-validation ดอก 1–7 ไม่ได้หยุดตามจุดต่ำสุดของดอก 7
              เพื่อให้ดอก 7 ยังเป็นเกณฑ์ gate ที่ไม่ลำเอียง) · กราฟละเอียด (histogram น้ำหนัก, โครงข่าย) ดูใน TensorBoard
            </p>
          </>
        ) : (
          <p className="text-xs text-gray-400">เวอร์ชันนี้ไม่มีประวัติการเทรน</p>
        )}
      </Card>

      <Card title="งาน retrain (trainer-worker, GPU)" right={<Link to="/tool-vision?tab=model" className="text-xs text-indigo-600 font-semibold">เริ่ม retrain / promote ที่ Tool Inspection →</Link>}>
        {jobs.length === 0 ? (
          <p className="text-xs text-gray-400">ยังไม่มีงาน retrain</p>
        ) : (
          <div className="space-y-3">
            {jobs.map((j) => {
              const live = j.status === 'QUEUED' || j.status === 'RUNNING';
              const hist = live ? j.progress?.history : j.result?.history;
              const r = j.result;
              const isVb = r?.metrics?.val?.mae != null;
              return (
                <details key={j.id} open={live} className="rounded-lg border border-gray-100 p-3">
                  <summary className="cursor-pointer text-xs flex flex-wrap items-center gap-2">
                    <b>{j.id}</b>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${live ? 'bg-amber-100 text-amber-700' : j.status === 'FAILED' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'}`}>{j.status}</span>
                    {live && j.progress && (
                      <span className="text-amber-700">
                        {j.progress.stage === 'evaluating' ? 'กำลังประเมิน candidate…' : `epoch ${j.progress.epoch}/${j.progress.epochs}`}
                      </span>
                    )}
                    {isVb && (
                      <span className="text-gray-500">
                        MAE ดอก 7: {r!.metrics.base_val.mae} → {r!.metrics.val.mae} µm · gate {r!.gate.passed ? 'ผ่าน' : 'ไม่ผ่าน'}
                      </span>
                    )}
                    <span className="text-gray-400">
                      · {j.requested_by} · {fmtDateTime(j.requested_at)} · ค่าวัด {j.n_labels} ใบ
                    </span>
                  </summary>
                  <div className="mt-3">
                    {live && j.progress && (
                      <div className="h-1.5 rounded bg-gray-100 overflow-hidden mb-3">
                        <div className="h-full bg-amber-500 transition-all" style={{ width: `${(100 * j.progress.epoch) / Math.max(1, j.progress.epochs)}%` }} />
                      </div>
                    )}
                    {hist?.length ? (
                      <TrainingCurves history={hist} epochs={j.progress?.epochs_per_member ?? j.progress?.epochs} height={160} />
                    ) : (
                      <p className="text-xs text-gray-400">{live ? 'รอ epoch แรก…' : 'ไม่มีประวัติการเทรน'}</p>
                    )}
                    {j.error && <p className="text-xs text-red-600 mt-2">{j.error}</p>}
                  </div>
                </details>
              );
            })}
          </div>
        )}
      </Card>

      <Card title="เวอร์ชัน (models/tool-vision/ ใน MinIO)">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-100">
                <th className="py-2 pr-2">เวอร์ชัน</th>
                <th className="py-2 pr-2">สถานะ</th>
                <th className="py-2 pr-2">สร้างเมื่อ</th>
                <th className="py-2 pr-2 text-right">MAE ดอก 7</th>
                <th className="py-2 pr-2 text-right">MAE test</th>
                <th className="py-2 pr-2 text-right">ค่าวัดจากคน</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => {
                const st = v.active ? VERSION_STATUS.production : VERSION_STATUS[v.status ?? ''] ?? VERSION_STATUS.previous;
                return (
                  <tr key={v.version} className={`border-b border-gray-50 ${v.active ? 'bg-emerald-50/40' : ''}`}>
                    <td className="py-2 pr-2 font-mono">
                      {v.version}
                      <span className="block text-[10px] text-gray-400 font-sans">{v.base_version ? `retrain จาก ${v.base_version}` : 'ฝึกจากชุดข้อมูล (ดอก 1–6)'}</span>
                    </td>
                    <td className="py-2 pr-2">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${st.cls}`}>{st.label}</span>
                    </td>
                    <td className="py-2 pr-2">{fmtDateTime(v.created_utc)}</td>
                    <td className="py-2 pr-2 text-right tabular-nums">{fmt(v.val_mae, 1)}</td>
                    <td className="py-2 pr-2 text-right tabular-nums">{fmt(v.test_mae, 1)}</td>
                    <td className="py-2 pr-2 text-right tabular-nums">{v.n_human_labels ?? 0}</td>
                    <td className="py-2 text-right whitespace-nowrap">
                      {v.history?.length ? (
                        <button onClick={() => setSel(v.version)} className="btn-secondary mr-1">
                          กราฟ
                        </button>
                      ) : null}
                      {v.status === 'candidate' && !v.active ? (
                        <Link to="/tool-vision?tab=model" className="text-[11px] text-indigo-600 font-semibold">
                          Promote / Reject →
                        </Link>
                      ) : (
                        !v.active &&
                        isAdmin && (
                          <button
                            disabled={busy}
                            onClick={() => confirm(`ใช้ ${v.version} เป็นแบบจำลองหลัก?`) && act(() => api.activateVisionVersion(v.version))}
                            className="btn-secondary"
                          >
                            ใช้เวอร์ชันนี้
                          </button>
                        )
                      )}
                    </td>
                  </tr>
                );
              })}
              {versions.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-3 text-gray-400">
                    ไม่มีแบบจำลองใน MinIO
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <p className="text-[10px] text-gray-400 mt-2">
            retrain ที่ผ่านการ Promote จะเพิ่มเป็นเวอร์ชันใหม่ · เวอร์ชันเก่าเก็บไว้ทั้งหมดเพื่อสลับกลับได้
            {!isAdmin && ' · การสลับเวอร์ชันใช้ได้เฉพาะผู้ดูแลระบบ'}
          </p>
        </div>
      </Card>
    </div>
  );
};

export default VisionRegistry;
