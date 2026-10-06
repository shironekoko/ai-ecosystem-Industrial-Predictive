/**
 * ใบเบิกดอกกัด (Tool Requisition) ขนาด A4 — แสดงในหน้าเว็บและแปลงเป็น PDF ในเบราว์เซอร์
 * ใช้ style แบบ inline (สี hex) ทั้งหมด เพื่อให้ html2canvas วาดได้ตรงกับที่เห็น · ภาษาไทยใช้ฟอนต์ของหน้าเว็บ (ไม่ต้องฝังฟอนต์ใน PDF)
 */
import React, { forwardRef } from 'react';
import type { Requisition, RequisitionStatus, ToolVerdict } from '../../types';

export const REQ_STATUS: Record<RequisitionStatus, { th: string; color: string; bg: string }> = {
  OPEN: { th: 'รอเบิก', color: '#b45309', bg: '#fef3c7' },
  ISSUED: { th: 'เบิกแล้ว รอติดตั้ง', color: '#1d4ed8', bg: '#dbeafe' },
  INSTALLED: { th: 'ติดตั้งแล้ว', color: '#047857', bg: '#d1fae5' },
};

const VERDICT_TH: Record<ToolVerdict, string> = {
  OK: 'ปกติ (VB เฉลี่ย < 103 µm)',
  MONITOR: 'ใกล้หมดอายุ (VB เฉลี่ย 103–140 µm)',
  REPLACE: 'หมดอายุ (VB เฉลี่ย ≥ 140 µm)',
};

/** วันที่แบบเอกสารราชการไทย (พ.ศ.) */
const thDate = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString('th-TH', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';

const C = { ink: '#111827', muted: '#6b7280', line: '#d1d5db', head: '#f3f4f6', accent: '#4338ca' };
const cell: React.CSSProperties = { border: `1px solid ${C.line}`, padding: '6px 8px' };
const th: React.CSSProperties = { ...cell, background: C.head, fontWeight: 600, textAlign: 'left' };
const h2: React.CSSProperties = { fontSize: 14, fontWeight: 700, margin: '18px 0 8px', color: C.accent };

const Sign: React.FC<{ role: string; name?: string | null; at?: string | null }> = ({ role, name, at }) => (
  <div style={{ flex: 1, textAlign: 'center', fontSize: 12 }}>
    <div style={{ fontWeight: 600, marginBottom: 34 }}>{role}</div>
    <div style={{ borderTop: `1px dotted ${C.ink}`, margin: '0 10px', paddingTop: 4 }}>({name || ' '.repeat(28)})</div>
    <div style={{ color: C.muted, marginTop: 4 }}>วันที่ {thDate(at) || '.........................'}</div>
  </div>
);

export const RequisitionDoc = forwardRef<HTMLDivElement, { r: Requisition }>(({ r }, ref) => {
  const st = REQ_STATUS[r.status];
  const removal =
    r.removal_reason === 'REPLACED_BY_OPERATOR'
      ? `ผู้ควบคุม ${r.removed_by ?? '—'} ถอดดอกตามคำแนะนำของแบบจำลอง RUL (${r.rul_recommendation ?? '—'})`
      : 'ถอดเมื่อสิ้นสุดข้อมูลการทดลอง';
  return (
    <div
      ref={ref}
      style={{
        width: 794,
        minHeight: 1123,
        boxSizing: 'border-box',
        padding: '44px 52px',
        background: '#ffffff',
        color: C.ink,
        fontFamily: "'Prompt', 'Tahoma', sans-serif",
        fontSize: 12.5,
        lineHeight: 1.55,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* หัวเอกสาร */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: `2px solid ${C.ink}`, paddingBottom: 12 }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>ใบเบิกดอกกัด</div>
          <div style={{ fontSize: 13, color: C.muted }}>Tool Requisition · ระบบ AI Ecosystem — CNC Tool Life</div>
        </div>
        <div style={{ textAlign: 'right', fontSize: 12.5 }}>
          <div>
            เลขที่ <b style={{ fontSize: 15 }}>{r.req_no}</b>
          </div>
          <div>วันที่ออก {thDate(r.created_at)}</div>
          <div style={{ display: 'inline-block', marginTop: 6, padding: '2px 10px', borderRadius: 4, background: st.bg, color: st.color, fontWeight: 700 }}>{st.th}</div>
        </div>
      </div>

      <div style={h2}>1. รายการที่ขอเบิก</div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ ...th, width: 50, textAlign: 'center' }}>ลำดับ</th>
            <th style={th}>รายการ</th>
            <th style={{ ...th, width: 70, textAlign: 'center' }}>จำนวน</th>
            <th style={{ ...th, width: 70, textAlign: 'center' }}>หน่วย</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style={{ ...cell, textAlign: 'center' }}>1</td>
            <td style={cell}>
              ดอกกัด (end mill) 4 คม — ชนิดเดียวกับดอก {r.tool_ref ?? '—'} ที่ถอดออก
              <div style={{ color: C.muted, fontSize: 11.5 }}>ใช้กับเครื่อง {r.machine_id} · ทดแทนดอก {r.tool_ref ?? '—'}</div>
            </td>
            <td style={{ ...cell, textAlign: 'center' }}>1</td>
            <td style={{ ...cell, textAlign: 'center' }}>ดอก</td>
          </tr>
        </tbody>
      </table>

      <div style={h2}>2. เหตุผลการเบิก</div>
      <div>
        ดอก {r.tool_ref ?? '—'} ถูกถอดจากเครื่อง {r.machine_id} เมื่อเวลาตัดสะสม {r.removed_t_min != null ? r.removed_t_min.toFixed(1) : '—'} นาที ({thDate(r.removed_at)}) — {removal}
      </div>
      <div style={{ marginTop: 4 }}>
        ผลตรวจใบมีด {r.inspection_id} ยืนยันโดย {r.requested_by ?? '—'} ({thDate(r.reviewed_at)}) — รอยสึกด้านข้าง VB ของแต่ละใบมีด:
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 8 }}>
        <thead>
          <tr>
            <th style={th}>ใบมีด</th>
            {r.blades.map((b) => (
              <th key={b.blade} style={{ ...th, textAlign: 'center' }}>
                B{b.blade}
              </th>
            ))}
            <th style={{ ...th, textAlign: 'center' }}>เฉลี่ย 4 ใบ</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style={cell}>VB (µm)</td>
            {r.blades.map((b) => (
              <td key={b.blade} style={{ ...cell, textAlign: 'center', fontWeight: r.worst_blade === b.blade ? 700 : 400 }}>
                {b.final_vb != null ? b.final_vb.toFixed(1) : '—'}
              </td>
            ))}
            <td style={{ ...cell, textAlign: 'center', fontWeight: 700 }}>{r.mean_vb != null ? r.mean_vb.toFixed(1) : '—'}</td>
          </tr>
          <tr>
            <td style={cell}>ที่มาของค่า</td>
            {r.blades.map((b) => (
              <td key={b.blade} style={{ ...cell, textAlign: 'center', color: C.muted }}>
                {b.vb_source === 'AI' ? 'AI (ผู้ตรวจยอมรับ)' : 'ผู้ตรวจวัด'}
              </td>
            ))}
            <td style={cell} />
          </tr>
        </tbody>
      </table>
      <div style={{ marginTop: 8 }}>
        ระดับดอก: <b>{r.verdict ? VERDICT_TH[r.verdict] : '—'}</b>
        {r.worst_blade != null && ` · คมที่สึกมากสุด B${r.worst_blade} ${r.worst_vb?.toFixed(1)} µm`}
        {r.over_limit.length > 0 && ` · คมที่เกิน 140 µm เฉพาะใบ: ${r.over_limit.map((b) => `B${b}`).join(', ')}`}
      </div>
      {r.note && <div style={{ marginTop: 4, color: C.muted }}>หมายเหตุผู้ตรวจ: {r.note}</div>}

      <div style={h2}>3. การจัดการดอกที่ถอด</div>
      <div style={{ border: `1px solid ${C.line}`, padding: '8px 10px', background: C.head }}>{r.disposition ?? '—'}</div>

      <div style={h2}>4. ลงนาม</div>
      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <Sign role="ผู้ขอเบิก" name={r.requested_by} at={r.created_at} />
        <Sign role="ผู้อนุมัติ" />
        <Sign role="ผู้จ่าย (คลังเครื่องมือ)" name={r.issued_by} at={r.issued_at} />
        <Sign role="ผู้ติดตั้งดอก" name={r.installed_by} at={r.installed_at} />
      </div>

      <div style={{ marginTop: 'auto', paddingTop: 18, borderTop: `1px solid ${C.line}`, fontSize: 10.5, color: C.muted }}>
        ออกโดยระบบจากผลตรวจใบมีด {r.inspection_id} · แบบจำลอง RUL {r.rul_model_version ?? '—'} · แบบจำลองวัด VB {r.vision_model_version} ·{' '}
        <span style={{ whiteSpace: 'nowrap' }}>พิมพ์เมื่อ {thDate(new Date().toISOString())}</span>
      </div>
    </div>
  );
});
RequisitionDoc.displayName = 'RequisitionDoc';

/** แปลงใบเบิก (element ขนาด A4) เป็นไฟล์ PDF 1 หน้าแล้วดาวน์โหลด — โหลดไลบรารีเมื่อกดเท่านั้น */
export async function downloadRequisitionPdf(el: HTMLElement, reqNo: string) {
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([import('html2canvas'), import('jspdf')]);
  await document.fonts?.ready;
  const canvas = await html2canvas(el, { scale: 2, backgroundColor: '#ffffff', logging: false });
  const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const pw = pdf.internal.pageSize.getWidth();
  const ph = pdf.internal.pageSize.getHeight();
  const k = Math.min(pw / canvas.width, ph / canvas.height);
  pdf.setProperties({ title: `ใบเบิกดอกกัด ${reqNo}`, subject: 'Tool requisition', creator: 'AI Ecosystem — CNC Tool Life' });
  pdf.addImage(canvas.toDataURL('image/jpeg', 0.95), 'JPEG', (pw - canvas.width * k) / 2, 0, canvas.width * k, canvas.height * k);
  pdf.save(`${reqNo}.pdf`);
}
