/**
 * Tool Image Wear — หน้าจองไว้สำหรับแบบจำลองประเมินการสึกหรอจากภาพใบมีด (ทีมพัฒนาอีกคนรับผิดชอบ)
 *
 * ยังไม่มีแบบจำลอง จึงไม่มีการแสดงผลลัพธ์ใด ๆ (ไม่มีข้อมูลตัวอย่าง/ค่าสมมุติ)
 * จุดเชื่อมต่อที่เตรียมไว้: MinIO bucket "qc-verified" (ภาพ), "models" (แบบจำลอง), alarms/audit API ที่มีอยู่
 */
import React from 'react';
import { Camera, Construction, Database, GitMerge, ScanEye } from 'lucide-react';
import { PageHeader } from '../../components/common';
import { Card } from '../../components/toollife/ui';

const Step: React.FC<{ icon: React.FC<{ className?: string }>; title: string; text: string }> = ({ icon: Icon, title, text }) => (
  <div className="flex gap-3">
    <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
      <Icon className="w-4.5 h-4.5" />
    </div>
    <div>
      <p className="text-sm font-semibold text-gray-800">{title}</p>
      <p className="text-xs text-gray-500 leading-relaxed">{text}</p>
    </div>
  </div>
);

export const ToolVisionPage: React.FC = () => (
  <div className="space-y-5">
    <PageHeader title="Tool Image Wear" subtitle="ประเมินการสึกหรอจากภาพใบมีด (computer vision) — อยู่ระหว่างพัฒนา" />

    <div className="p-6 rounded-xl border-2 border-dashed border-gray-300 bg-white flex flex-col items-center text-center">
      <div className="w-14 h-14 rounded-2xl bg-amber-50 flex items-center justify-center mb-3">
        <Construction className="w-7 h-7 text-amber-600" />
      </div>
      <p className="text-base font-bold text-gray-800">ยังไม่มีแบบจำลองภาพใบมีด</p>
      <p className="text-sm text-gray-500 mt-1 max-w-xl">
        หน้านี้จองไว้ให้แบบจำลองที่ใช้ภาพถ่ายใบมีดเพื่อประเมินความสึกหรอ ซึ่งนักพัฒนาอีกท่านจะเป็นผู้สร้าง — ตอนนี้ระบบใช้แบบจำลองอนุกรมเวลา (RUL) จากเซนเซอร์เพียงตัวเดียว
      </p>
    </div>

    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card title="ขอบเขตที่วางไว้">
        <div className="space-y-4">
          <Step icon={Camera} title="อินพุต" text="ภาพด้านข้างคมตัด (flank face) จากกล้องจุลทรรศน์/กล้องในเครื่อง เมื่อถอดดอกหรือระหว่างหยุดเครื่องตามแผน" />
          <Step icon={ScanEye} title="เอาต์พุต" text="ค่า VB ที่วัดจากภาพ (µm) และ/หรือระดับความสึก เพื่อยืนยันการเปลี่ยนดอกและสร้าง label ให้แบบจำลองอนุกรมเวลา" />
          <Step icon={GitMerge} title="การเชื่อมกับแบบจำลอง RUL" text="ผลจากภาพใช้เป็นค่าจริง (ground truth) หลังถอดดอก — แบบจำลอง RUL ยังคงใช้เฉพาะข้อมูลเซนเซอร์ระหว่างการตัด" />
        </div>
      </Card>
      <Card title="จุดเชื่อมต่อที่มีอยู่แล้วในระบบ">
        <div className="space-y-4">
          <Step icon={Database} title="MinIO" text='bucket "qc-verified" สำหรับภาพที่ตรวจแล้ว และ "models" สำหรับเก็บแบบจำลองแยก prefix ของตัวเอง (เช่น tool-vision/)' />
          <Step icon={Database} title="API" text="Alarms / Audit Trail / Auth ใช้ร่วมกันได้ทันที — เพิ่ม router ใหม่ใน backend/app/features/ ตามโครงสร้างเดิม" />
        </div>
      </Card>
    </div>
  </div>
);

export default ToolVisionPage;
