import React from 'react';
import type { Recommendation, StreamConnectionStatus, StreamState, WearState } from '../../types';

export const fmt = (v: number | null | undefined, d = 1) => (v === null || v === undefined || Number.isNaN(v) ? '—' : v.toFixed(d));

export const fmtClock = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';

export const fmtDateTime = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString('th-TH', { dateStyle: 'short', timeStyle: 'medium' }) : '—';

export const STATE_STYLE: Record<WearState, { label: string; th: string; cls: string; color: string }> = {
  STEADY: { label: 'Steady wear', th: 'สึกปกติ', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', color: '#10b981' },
  ACCELERATED: { label: 'Accelerated', th: 'สึกเร่ง', cls: 'bg-amber-50 text-amber-700 border-amber-200', color: '#f59e0b' },
  END_OF_LIFE: { label: 'End of life', th: 'หมดอายุ', cls: 'bg-red-50 text-red-700 border-red-200', color: '#ef4444' },
};

export const REC_STYLE: Record<Recommendation, { label: string; th: string; cls: string }> = {
  OK: { label: 'OK', th: 'ใช้งานต่อได้', cls: 'bg-emerald-600 text-white' },
  WATCH: { label: 'WATCH', th: 'เฝ้าระวัง', cls: 'bg-amber-500 text-white' },
  PLAN_REPLACEMENT: { label: 'PLAN', th: 'วางแผนเปลี่ยนดอก', cls: 'bg-orange-600 text-white' },
  REPLACE_NOW: { label: 'REPLACE NOW', th: 'เปลี่ยนดอกทันที', cls: 'bg-red-600 text-white animate-pulse' },
};

export const STREAM_STYLE: Record<StreamState, { th: string; cls: string; dot: string }> = {
  IDLE: { th: 'รอเริ่ม', cls: 'text-gray-600 bg-gray-50 border-gray-200', dot: 'bg-gray-400' },
  CUTTING: { th: 'กำลังตัด', cls: 'text-emerald-700 bg-emerald-50 border-emerald-200', dot: 'bg-emerald-500 animate-pulse' },
  PAUSED: { th: 'หยุดชั่วคราว', cls: 'text-amber-700 bg-amber-50 border-amber-200', dot: 'bg-amber-500' },
  HOLD: { th: 'Interlock: รอผู้ควบคุม', cls: 'text-red-700 bg-red-50 border-red-200', dot: 'bg-red-500 animate-pulse' },
  COMPLETED: { th: 'ถอดดอกแล้ว', cls: 'text-indigo-700 bg-indigo-50 border-indigo-200', dot: 'bg-indigo-500' },
  ERROR: { th: 'ผิดพลาด', cls: 'text-red-700 bg-red-50 border-red-200', dot: 'bg-red-600' },
};

export const MACHINE_COLOR: Record<number, string> = { 1: '#6366f1', 2: '#0ea5e9', 3: '#14b8a6' };

export const WearBadge: React.FC<{ state?: WearState | null }> = ({ state }) =>
  state ? (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${STATE_STYLE[state].cls}`}>
      {STATE_STYLE[state].th}
    </span>
  ) : null;

export const RecBadge: React.FC<{ rec?: Recommendation | null; size?: 'sm' | 'md' }> = ({ rec, size = 'sm' }) =>
  rec ? (
    <span className={`inline-flex items-center rounded-md font-bold tracking-wide ${size === 'md' ? 'px-2.5 py-1 text-xs' : 'px-2 py-0.5 text-[10px]'} ${REC_STYLE[rec].cls}`}>
      {REC_STYLE[rec].label}
    </span>
  ) : null;

export const StreamBadge: React.FC<{ state: StreamState; speed?: number }> = ({ state, speed }) => (
  <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium border ${STREAM_STYLE[state].cls}`}>
    <span className={`w-1.5 h-1.5 rounded-full ${STREAM_STYLE[state].dot}`} />
    {STREAM_STYLE[state].th}
    {speed !== undefined && state === 'CUTTING' && <span className="text-gray-500">· {speed === 1 ? 'เวลาจริง' : `${speed}×`}</span>}
  </span>
);

export const ConnBadge: React.FC<{ conn: StreamConnectionStatus }> = ({ conn }) => {
  const s =
    conn === 'CONNECTED'
      ? { t: 'Live stream', c: 'bg-emerald-50 text-emerald-700 border-emerald-200', d: 'bg-emerald-500 animate-pulse' }
      : conn === 'CONNECTING'
      ? { t: 'Connecting…', c: 'bg-amber-50 text-amber-700 border-amber-200', d: 'bg-amber-500' }
      : { t: 'Disconnected', c: 'bg-red-50 text-red-700 border-red-200', d: 'bg-red-500' };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${s.c}`}>
      <span className={`w-2 h-2 rounded-full ${s.d}`} />
      {s.t}
    </span>
  );
};

export const Card: React.FC<{ title?: React.ReactNode; right?: React.ReactNode; className?: string; children: React.ReactNode }> = ({
  title,
  right,
  className = '',
  children,
}) => (
  <div className={`bg-white rounded-xl border border-gray-200 shadow-sm ${className}`}>
    {(title || right) && (
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between gap-3">
        <div className="text-sm font-semibold text-gray-800">{title}</div>
        {right}
      </div>
    )}
    <div className="p-4">{children}</div>
  </div>
);

export const PHASE_TEXT = {
  BREAK_IN: 'ช่วง break-in ของดอกใหม่ (ชั้นงานแรก) — ยังไม่พยากรณ์',
  BASELINE: 'กำลังเก็บค่าตั้งต้นของดอก',
  MONITOR: 'ติดตามอายุ',
} as const;
