/**
 * กราฟการฝึกแบบจำลองวัด VB รายรอบ (epoch): loss ชุดฝึก/validation, MAE บน validation (µm) และ learning rate
 * ข้อมูลมาจาก history ใน meta.json ของแต่ละเวอร์ชัน หรือความคืบหน้าสดของงาน retrain (Redis)
 * ensemble (history มี member): แกน x = epoch ของแต่ละสมาชิก, loss = ค่าเฉลี่ยของสมาชิก, MAE = เส้นของแต่ละสมาชิก + ค่าเฉลี่ย
 */
import React from 'react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TrainEpoch } from '../../types';

const AXIS = { fontSize: 10, fill: '#6b7280' };
const MEMBER_COLORS = ['#10b981', '#06b6d4', '#8b5cf6', '#f97316', '#ec4899', '#84cc16', '#64748b'];

type Row = { epoch: number; train_loss?: number; val_loss?: number; val_mae?: number; lr?: number; [k: string]: number | undefined };

const mean = (xs: (number | undefined)[]) => {
  const v = xs.filter((x): x is number => x != null);
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : undefined;
};

/** ensemble → แถวตาม epoch ของสมาชิก (ค่าเฉลี่ย + val MAE ของแต่ละสมาชิก) · แบบจำลองเดี่ยว → ข้อมูลเดิม */
function toRows(history: TrainEpoch[]): { rows: Row[]; members: number[] } {
  const members = [...new Set(history.map((h) => h.member ?? 1))].sort((a, b) => a - b);
  if (members.length <= 1) return { rows: history as Row[], members: [] };
  const start: Record<number, number> = {};
  history.forEach((h) => {
    const m = h.member ?? 1;
    start[m] = Math.min(start[m] ?? Infinity, h.epoch);
  });
  const byEpoch = new Map<number, TrainEpoch[]>();
  history.forEach((h) => {
    const e = h.epoch - start[h.member ?? 1] + 1;
    byEpoch.set(e, [...(byEpoch.get(e) ?? []), h]);
  });
  const rows = [...byEpoch.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([epoch, hs]) => {
      const r: Row = { epoch, train_loss: mean(hs.map((h) => h.train_loss)), val_loss: mean(hs.map((h) => h.val_loss)),
        val_mae: mean(hs.map((h) => h.val_mae)), lr: hs[0].lr };
      hs.forEach((h) => (r[`m${h.member}`] = h.val_mae ?? undefined));
      return r;
    });
  return { rows, members };
}

/** epochs = จำนวน epoch ที่ตั้งไว้ของแบบจำลอง 1 ตัว (ensemble: ต่อสมาชิก) — ใช้กำหนดความยาวแกน x ระหว่างฝึกสด */
export const TrainingCurves: React.FC<{ history: TrainEpoch[]; epochs?: number; height?: number; compact?: boolean }> = ({
  history,
  epochs,
  height = 190,
  compact = false,
}) => {
  if (!history?.length) return <p className="text-xs text-gray-400">ยังไม่มีข้อมูลการฝึก</p>;
  const { rows, members } = toRows(history);
  const ens = members.length > 1;
  const xMax = Math.max(epochs ?? 0, rows[rows.length - 1].epoch);   // epochs = จำนวน epoch ของสมาชิก 1 ตัว
  const hasVal = rows.some((h) => h.val_mae != null);
  const hasLr = rows.some((h) => h.lr != null);
  const best = hasVal ? rows.reduce((b, h) => (h.val_mae != null && (b == null || h.val_mae < b.val_mae!) ? h : b), null as Row | null) : null;
  const last = hasVal ? [...rows].reverse().find((h) => h.val_mae != null) : undefined;
  const xAxis = <XAxis dataKey="epoch" type="number" domain={[1, xMax]} tick={AXIS} allowDecimals={false} label={compact ? undefined : { value: ens ? 'epoch ของแต่ละสมาชิก' : 'epoch', position: 'insideBottomRight', offset: -2, fontSize: 10 }} />;
  const charts = [
    <div key="loss">
      <p className="text-[11px] font-semibold text-gray-600 mb-1">Loss (Huber บน VB/100){ens && <span className="font-normal text-gray-400"> · เฉลี่ย {members.length} สมาชิก</span>}</p>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="#f1f5f9" />
          {xAxis}
          <YAxis tick={AXIS} width={44} tickFormatter={(v) => v.toFixed(2)} />
          <Tooltip formatter={(v: number) => v.toFixed(4)} labelFormatter={(l) => `epoch ${l}`} />
          {!compact && <Legend wrapperStyle={{ fontSize: 10 }} />}
          <Line type="monotone" dataKey="train_loss" name="train" stroke="#6366f1" dot={false} strokeWidth={2} isAnimationActive={false} />
          {hasVal && <Line type="monotone" dataKey="val_loss" name="validation (ดอก 7)" stroke="#f59e0b" dot={false} strokeWidth={2} isAnimationActive={false} />}
        </LineChart>
      </ResponsiveContainer>
    </div>,
  ];
  if (hasVal)
    charts.push(
      <div key="mae">
        <p className="text-[11px] font-semibold text-gray-600 mb-1">
          MAE บน validation (µm){ens && ' รายสมาชิก'}
          {last && (
            <span className="font-normal text-gray-400">
              {' '}
              · epoch สุดท้าย {last.val_mae!.toFixed(1)}
              {ens && ' (เฉลี่ยรายตัว)'}
              {best && best.epoch !== last.epoch && ` · ต่ำสุด ${best.val_mae!.toFixed(1)} ที่ epoch ${best.epoch}`}
            </span>
          )}
        </p>
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#f1f5f9" />
            {xAxis}
            <YAxis tick={AXIS} width={40} />
            <Tooltip formatter={(v: number) => `${v.toFixed(1)} µm`} labelFormatter={(l) => `epoch ${l}`} />
            {ens && !compact && <Legend wrapperStyle={{ fontSize: 10 }} />}
            {members.map((m, i) => (
              <Line key={m} type="monotone" dataKey={`m${m}`} name={`สมาชิก ${m}`} stroke={MEMBER_COLORS[i % MEMBER_COLORS.length]} dot={false} strokeWidth={1} strokeOpacity={0.55} isAnimationActive={false} />
            ))}
            <Line type="monotone" dataKey="val_mae" name={ens ? 'เฉลี่ย' : 'val MAE'} stroke={ens ? '#111827' : '#10b981'} dot={ens ? false : { r: 2 }} strokeWidth={2} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>,
    );
  if (hasLr && !compact)
    charts.push(
      <div key="lr">
        <p className="text-[11px] font-semibold text-gray-600 mb-1">Learning rate (warm-up + cosine decay)</p>
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#f1f5f9" />
            {xAxis}
            <YAxis tick={AXIS} width={52} tickFormatter={(v) => v.toExponential(0)} />
            <Tooltip formatter={(v: number) => v.toExponential(2)} labelFormatter={(l) => `epoch ${l}`} />
            <Line type="monotone" dataKey="lr" name="lr" stroke="#8b5cf6" dot={false} strokeWidth={2} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>,
    );
  return <div className={`grid grid-cols-1 ${charts.length >= 3 ? 'lg:grid-cols-3' : charts.length === 2 ? 'md:grid-cols-2' : ''} gap-4`}>{charts}</div>;
};

export default TrainingCurves;
