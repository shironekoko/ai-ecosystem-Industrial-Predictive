/**
 * กราฟการฝึกแบบจำลองวัด VB รายรอบ (epoch): loss ชุดฝึก/validation, MAE บน validation (µm) และ learning rate
 * ข้อมูลมาจาก history ใน meta.json ของแต่ละเวอร์ชัน หรือความคืบหน้าสดของงาน retrain (Redis)
 */
import React from 'react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TrainEpoch } from '../../types';

const AXIS = { fontSize: 10, fill: '#6b7280' };

export const TrainingCurves: React.FC<{ history: TrainEpoch[]; epochs?: number; height?: number; compact?: boolean }> = ({
  history,
  epochs,
  height = 190,
  compact = false,
}) => {
  if (!history?.length) return <p className="text-xs text-gray-400">ยังไม่มีข้อมูลการฝึก</p>;
  const xMax = Math.max(epochs ?? 0, history[history.length - 1].epoch);
  const hasVal = history.some((h) => h.val_mae != null);
  const hasLr = history.some((h) => h.lr != null);
  const best = hasVal ? history.reduce((b, h) => (h.val_mae != null && (b == null || h.val_mae < b.val_mae!) ? h : b), null as TrainEpoch | null) : null;
  const last = hasVal ? [...history].reverse().find((h) => h.val_mae != null) : undefined;
  const xAxis = <XAxis dataKey="epoch" type="number" domain={[1, xMax]} tick={AXIS} allowDecimals={false} label={compact ? undefined : { value: 'epoch', position: 'insideBottomRight', offset: -2, fontSize: 10 }} />;
  const charts = [
    <div key="loss">
      <p className="text-[11px] font-semibold text-gray-600 mb-1">Loss (Huber บน VB/100)</p>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={history} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
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
          MAE บน validation (µm)
          {last && (
            <span className="font-normal text-gray-400">
              {' '}
              · epoch สุดท้าย {last.val_mae!.toFixed(1)}
              {best && best.epoch !== last.epoch && ` · ต่ำสุด ${best.val_mae!.toFixed(1)} ที่ epoch ${best.epoch}`}
            </span>
          )}
        </p>
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={history} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#f1f5f9" />
            {xAxis}
            <YAxis tick={AXIS} width={40} />
            <Tooltip formatter={(v: number) => `${v.toFixed(1)} µm`} labelFormatter={(l) => `epoch ${l}`} />
            <Line type="monotone" dataKey="val_mae" name="val MAE" stroke="#10b981" dot={{ r: 2 }} strokeWidth={2} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>,
    );
  if (hasLr && !compact)
    charts.push(
      <div key="lr">
        <p className="text-[11px] font-semibold text-gray-600 mb-1">Learning rate (warm-up + cosine decay)</p>
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={history} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
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
