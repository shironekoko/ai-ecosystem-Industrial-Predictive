import React, { useEffect, useState } from 'react';
import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { CheckCircle2, Download, FileBarChart, Timer, TriangleAlert, Wrench } from 'lucide-react';
import { PageHeader, StatCard, EmptyState } from '../../components/common';
import { Card, MACHINE_COLOR, fmt, fmtDateTime } from '../../components/toollife/ui';
import { api } from '../../services/api';
import type { ToolEvaluation, ToolLifeSummary } from '../../types';

const EvalCard: React.FC<{ e: ToolEvaluation }> = ({ e }) => {
  const color = MACHINE_COLOR[e.machine] || '#6366f1';
  const data = (e.trajectory || []).map((p) => ({ t: p.t_min, rul: p.rul, band: [p.lo, p.hi], truth: p.rul_true }));
  return (
    <Card
      title={
        <span>
          M{e.machine} · ดอก T{e.tool} <span className="text-gray-400 font-normal">· {e.model_version}</span>
        </span>
      }
      right={<span className="text-[11px] text-gray-400">{fmtDateTime(e.completed_at)}</span>}
    >
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-center text-xs mb-3">
        <div className="p-2 rounded-lg bg-gray-50">
          <p className="text-gray-500">เวลาหมดอายุจริง (VB 140 µm)</p>
          <p className="font-bold text-base">{fmt(e.T_eol_true_min)} นาที</p>
        </div>
        <div className="p-2 rounded-lg bg-gray-50">
          <p className="text-gray-500">สั่ง REPLACE_NOW ครั้งแรก</p>
          <p className={`font-bold text-base ${e.replace_late ? 'text-red-600' : 'text-gray-900'}`}>{fmt(e.first_replace_now_min)} นาที</p>
          <p className="text-[10px] text-gray-400">{e.replace_margin_min != null ? `ก่อนหมดอายุ ${fmt(e.replace_margin_min)} นาที` : '—'}</p>
        </div>
        <div className="p-2 rounded-lg bg-gray-50">
          <p className="text-gray-500">MAE ของ RUL (ทั้งอายุ / 20% ท้าย)</p>
          <p className="font-bold text-base">
            {fmt(e.mae_min, 2)} / {fmt(e.mae_last20_min, 2)}
          </p>
        </div>
        <div className="p-2 rounded-lg bg-gray-50">
          <p className="text-gray-500">VB ตอนถอดดอก</p>
          <p className="font-bold text-base">{fmt(e.vb_at_removal_um, 0)} µm</p>
          <p className="text-[10px] text-gray-400">ใช้อายุไป {fmt(e.life_used_at_replace_pct, 0)}%</p>
        </div>
      </div>
      {data.length > 0 && (
        <div className="h-60">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#f1f5f9" />
              <XAxis
                dataKey="t"
                type="number"
                domain={['dataMin', (max: number) => Math.ceil(Math.max(max, (e.T_eol_true_min ?? 0) + 1))]}
                tick={{ fontSize: 10 }}
                tickFormatter={(v) => v.toFixed(0)}
              />
              <YAxis tick={{ fontSize: 10 }} width={36} />
              <Tooltip formatter={(v: any) => (Array.isArray(v) ? `${v[0].toFixed(1)}–${v[1].toFixed(1)}` : Number(v).toFixed(2))} labelFormatter={(l) => `เวลาตัด ${Number(l).toFixed(1)} นาที`} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Area dataKey="band" name="P10–P90" stroke="none" fill={color} fillOpacity={0.15} isAnimationActive={false} />
              <Line dataKey="rul" name="RUL ที่ระบบบอกระหว่างใช้งาน" stroke={color} dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line dataKey="truth" name="RUL จริง (จาก VB ที่วัดหลังถอดดอก)" stroke="#111827" strokeDasharray="5 4" dot={false} isAnimationActive={false} />
              {e.first_replace_now_min != null && <ReferenceLine x={e.first_replace_now_min} stroke="#ef4444" label={{ value: 'REPLACE_NOW', fontSize: 9, fill: '#ef4444' }} />}
              {e.T_eol_true_min != null && <ReferenceLine x={e.T_eol_true_min} stroke="#111827" label={{ value: 'EOL จริง', fontSize: 9 }} />}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
      <p className="text-[11px] text-gray-500 mt-2">
        {e.reason === 'REPLACED_BY_OPERATOR' ? 'ผู้ควบคุมถอดดอกตามคำแนะนำ' : 'เล่นจนสิ้นสุดข้อมูลการทดลอง'} · ช่วง P10–P90 ครอบค่าจริง {fmt(e.coverage_p10_p90_pct, 0)}% ของรัน · แจ้งวางแผนล่วงหน้า{' '}
        {fmt(e.plan_lead_min)} นาที · พยากรณ์เกินจริง &gt; 1 ชั้น {fmt(e.late_pct, 1)}% ของรัน
      </p>
    </Card>
  );
};

export const ReportsPage: React.FC = () => {
  const [summary, setSummary] = useState<ToolLifeSummary | null>(null);
  const [evals, setEvals] = useState<ToolEvaluation[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.getToolLifeSummary().then(setSummary).catch((e) => setErr(e.message));
    api.getEvaluations(true).then(setEvals).catch(() => {});
  }, []);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Reports"
        subtitle="ผลของแบบจำลองเทียบกับ VB ที่วัดจริง — คำนวณเฉพาะดอกที่ถูกถอดออกจากเครื่องแล้ว (ระหว่างใช้งานไม่มีการเปิดเผยค่าจริง)"
        actions={
          <button onClick={() => api.downloadEvaluationsCsv().catch((e) => setErr(e.message))} className="btn-secondary">
            <Download className="w-3.5 h-3.5" /> CSV
          </button>
        }
      />
      {err && <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{err}</div>}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label="ดอกที่ประเมินแล้ว" value={summary?.completedTools ?? 0} icon={FileBarChart} accent="indigo" trendLabel={`ถอดตามคำแนะนำ ${summary?.replacedByOperator ?? 0} ดอก`} />
        <StatCard label="เปลี่ยนช้าเกินเกณฑ์" value={summary?.lateReplacements ?? 0} icon={TriangleAlert} accent={summary?.lateReplacements ? 'red' : 'emerald'} trendLabel="REPLACE_NOW หลัง VB ถึง 140 µm" />
        <StatCard label="MAE ของ RUL" value={fmt(summary?.meanAbsRulErrorMin, 2)} unit="นาที" icon={Timer} accent="amber" trendLabel={`20% ท้าย ${fmt(summary?.meanRulErrorLast20Min, 2)} นาที`} />
        <StatCard label="อายุดอกที่ใช้ได้" value={fmt(summary?.meanLifeUsedAtReplacePct, 0)} unit="%" icon={Wrench} accent="emerald" trendLabel={`แจ้งวางแผนล่วงหน้า ${fmt(summary?.meanPlanLeadMin)} นาที`} />
      </div>
      {evals.length === 0 ? (
        <Card>
          <EmptyState
            icon={CheckCircle2}
            title="ยังไม่มีดอกที่ถอดออก"
            description="เมื่อผู้ควบคุมกด 'ถอดดอก' หรือสตรีมเล่นจนจบข้อมูล ระบบจะอ่าน VB ที่วัดจริงของดอกนั้นแล้วเทียบกับสิ่งที่แบบจำลองบอกไว้ระหว่างใช้งาน"
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {[...evals].reverse().map((e, i) => (
            <EvalCard key={`${e.tool}-${e.completed_at}-${i}`} e={e} />
          ))}
        </div>
      )}
    </div>
  );
};

export default ReportsPage;
