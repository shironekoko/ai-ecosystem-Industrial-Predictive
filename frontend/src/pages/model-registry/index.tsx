/**
 * Model Registry — แบบจำลองทั้งสองตัวของระบบที่ backend ดึงจาก MinIO (bucket "models")
 *   - Time series: GRU direct-RUL (prefix "tool-rul/")
 *   - Vision: ResNet-18 วัดรอยสึก VB จากภาพใบมีด (prefix "tool-vision/") + กราฟการเทรน + งาน retrain
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Activity, CheckCircle2, Database, ScanEye, RefreshCw, XCircle } from 'lucide-react';
import { PageHeader } from '../../components/common';
import { Card, fmt, fmtDateTime } from '../../components/toollife/ui';
import { api } from '../../services/api';
import type { ModelInfo, ModelVersion } from '../../types';
import { VisionRegistry } from './VisionRegistry';

export const ModelRegistryPage: React.FC = () => {
  const [params, setParams] = useSearchParams();
  const tab = params.get('model') === 'vision' ? 'vision' : 'rul';
  return (
    <div className="space-y-5">
      <PageHeader
        title="Model Registry"
        subtitle="แบบจำลองทั้งสองตัวของระบบ — เก็บทุกเวอร์ชันใน MinIO, backend ตรวจ sha256 + self-test ก่อนใช้งาน"
      />
      <div className="flex flex-wrap gap-1 p-1 bg-gray-100 rounded-lg w-fit">
        {(
          [
            ['rul', 'Time series — RUL ดอกกัด (GRU)', Activity],
            ['vision', 'Vision — วัดรอยสึก VB จากภาพ (ResNet-18)', ScanEye],
          ] as const
        ).map(([id, label, Icon]) => (
          <button
            key={id}
            onClick={() => setParams(id === 'rul' ? {} : { model: id })}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 ${tab === id ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-800'}`}
          >
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
      </div>
      {tab === 'rul' ? <RulRegistry /> : <VisionRegistry />}
    </div>
  );
};

const RulRegistry: React.FC = () => {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [versions, setVersions] = useState<ModelVersion[] | null>(null);
  const [vErr, setVErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.getModel().then(setInfo).catch(() => setInfo(null));
    api
      .getModelVersions()
      .then((v) => {
        setVersions(v);
        setVErr(null);
      })
      .catch((e) => setVErr(e.message));
  }, []);

  useEffect(load, [load]);

  const reload = async (version?: string) => {
    setBusy(true);
    try {
      setInfo(await api.reloadModel(version));
    } catch (e: any) {
      alert(e.message);
    } finally {
      setBusy(false);
      load();
    }
  };

  const meta = info?.meta;
  const ev = info?.evaluation;

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <button onClick={() => reload()} disabled={busy} className="btn-primary">
          <RefreshCw className={`w-3.5 h-3.5 ${busy ? 'animate-spin' : ''}`} /> ดึงเวอร์ชันล่าสุดจาก MinIO
        </button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card
          title={
            <span className="flex items-center gap-2">
              <Database className="w-4 h-4 text-indigo-500" /> แบบจำลองที่ใช้งานอยู่
            </span>
          }
          className="xl:col-span-1"
        >
          {!info ? (
            <p className="text-sm text-gray-400">เชื่อมต่อ backend ไม่ได้</p>
          ) : (
            <div className="space-y-2 text-xs">
              <div className="flex items-center gap-2">
                {info.status === 'READY' ? <CheckCircle2 className="w-5 h-5 text-emerald-600" /> : <XCircle className="w-5 h-5 text-red-600" />}
                <span className="text-sm font-bold">{info.status === 'READY' ? info.version : 'ไม่มีแบบจำลอง'}</span>
              </div>
              {info.error && <p className="text-red-600 break-all">{info.error}</p>}
              <Row k="แหล่ง" v={<span className="font-mono break-all">{info.source || '—'}</span>} />
              <Row k="โหลดเมื่อ" v={fmtDateTime(info.loaded_at)} />
              <Row k="sha256" v={<span className="font-mono">{info.sha256?.slice(0, 16) || '—'}…</span>} />
              <Row k="self-test" v={info.status === 'READY' ? 'ผ่าน (runtime ตรงกับตอนส่งออก)' : '—'} />
              {meta && (
                <>
                  <Row k="สถาปัตยกรรม" v={`${meta.architecture.type} (${meta.architecture.members} ตัว, hidden ${meta.architecture.hidden})`} />
                  <Row k="รูปแบบที่เลือก" v={`${meta.architecture.variant} · noise σ=${meta.architecture.input_noise_std}`} />
                  <Row k="หน้าต่างอินพุต" v={`${meta.architecture.window_runs} รัน (= 1 ชั้นงาน)`} />
                  <Row k="ดอกที่ใช้ฝึก" v={meta.train.tools.map((t: number) => `T${t}`).join(', ')} />
                  <Row k="ดอกที่สงวนไว้สตรีม" v={meta.train.held_out_stream_tools.map((t: number) => `T${t}`).join(', ')} />
                  <Row k="เกณฑ์" v={`สึกเร่ง VB ${meta.criteria.vb_accel_um} µm · หมดอายุ VB ${meta.criteria.vb_eol_um} µm`} />
                  <Row k="นโยบาย" v={`REPLACE_NOW: P10 ≤ ${fmt(meta.policy.replace_min, 2)} นาที · PLAN: P10 ≤ ${fmt(meta.policy.plan_min, 1)} นาที`} />
                </>
              )}
            </div>
          )}
        </Card>

        <Card title="อินพุต / เอาต์พุต" className="xl:col-span-2">
          {meta ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div>
                <p className="font-semibold text-gray-700 mb-1">อินพุตต่อรัน (12 ตัว) × 29 รันล่าสุด</p>
                <div className="flex flex-wrap gap-1">
                  {meta.inputs.features.map((f: string) => (
                    <span key={f} className="px-1.5 py-0.5 rounded bg-gray-100 font-mono text-[11px]">
                      {f}
                    </span>
                  ))}
                </div>
                <p className="text-gray-500 mt-2 leading-relaxed">{meta.inputs.note}</p>
              </div>
              <div>
                <p className="font-semibold text-gray-700 mb-1">เอาต์พุต</p>
                <ul className="list-disc pl-4 text-gray-600 space-y-1">
                  <li>เวลาตัดที่เหลือจนถึง VB = {meta.criteria.vb_eol_um} µm (RUL) และจนถึงช่วงสึกเร่ง</li>
                  <li>ข้อจำกัดฟิสิกส์: {meta.architecture.physics}</li>
                  <li>ช่วง P10–P90 จากความคลาดเคลื่อน leave-one-tool-out ของดอกฝึก</li>
                  <li>สถานะ STEADY / ACCELERATED / END_OF_LIFE และคำแนะนำ OK / WATCH / PLAN / REPLACE_NOW</li>
                </ul>
                <p className="text-gray-400 mt-2">{meta.criteria.reference}</p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-400">—</p>
          )}
        </Card>
      </div>

      <Card title="ผลประเมิน GRU direct-RUL — leave-one-tool-out (evaluation.json ใน MinIO, หน่วย นาทีของเวลาตัด)">
        {!ev?.loto ? (
          <p className="text-sm text-gray-400">ไม่มีไฟล์ผลประเมิน</p>
        ) : (
          <div className="space-y-2">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Stat label="MAE ทั้งอายุ" value={`${fmt(ev.loto.MAE_all, 2)} นาที`} />
              <Stat label="MAE 20% ท้ายอายุ" value={`${fmt(ev.loto.MAE_test20, 2)} นาที`} />
              <Stat label="Bias 20% ท้ายอายุ" value={`${fmt(ev.loto.Bias_test20, 2)} นาที`} hint="บวก = พยากรณ์เกินจริง" />
              <Stat label="พยากรณ์เกินจริง > 1 ชั้นงาน" value={`${fmt(ev.loto.Late_pct_test20, 1)}%`} hint="ในช่วง 20% ท้าย" />
            </div>
            <p className="text-[11px] text-gray-400">{ev.protocol}</p>
          </div>
        )}
      </Card>

      <Card title="เวอร์ชันทั้งหมดใน MinIO (models/tool-rul/)">
        {vErr ? (
          <p className="text-sm text-red-600">{vErr}</p>
        ) : !versions ? (
          <p className="text-sm text-gray-400">กำลังโหลด…</p>
        ) : versions.length === 0 ? (
          <p className="text-sm text-gray-400">ยังไม่มีแบบจำลองใน bucket — รัน scripts/publish_tool_rul_model.py</p>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-100">
                <th className="py-2">เวอร์ชัน</th>
                <th className="py-2">สร้างเมื่อ</th>
                <th className="py-2">ไฟล์</th>
                <th className="py-2">ดอกฝึก / สงวนไว้</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.version} className="border-b border-gray-50">
                  <td className="py-2 font-mono">
                    {v.version} {v.active && <span className="ml-1 px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 text-[10px]">latest</span>}
                  </td>
                  <td className="py-2">{fmtDateTime(v.created_utc)}</td>
                  <td className="py-2 text-gray-500">{v.files.map((f) => `${f.name} (${(f.size / 1024).toFixed(1)} KB)`).join(', ')}</td>
                  <td className="py-2">
                    {v.train_tools?.map((t) => `T${t}`).join(',')} / {v.held_out?.map((t) => `T${t}`).join(',')}
                  </td>
                  <td className="py-2 text-right">
                    {info?.version !== v.version && (
                      <button onClick={() => reload(v.version)} className="btn-secondary">
                        ใช้เวอร์ชันนี้
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
};

const Row: React.FC<{ k: string; v: React.ReactNode }> = ({ k, v }) => (
  <div className="flex justify-between gap-3">
    <span className="text-gray-500 shrink-0">{k}</span>
    <span className="text-gray-800 text-right">{v}</span>
  </div>
);

const Stat: React.FC<{ label: string; value: string; hint?: string }> = ({ label, value, hint }) => (
  <div className="rounded-lg border border-gray-100 bg-gray-50/60 p-3">
    <p className="text-[11px] text-gray-500">{label}</p>
    <p className="text-lg font-bold text-gray-900 tabular-nums">{value}</p>
    {hint && <p className="text-[10px] text-gray-400">{hint}</p>}
  </div>
);

export default ModelRegistryPage;
