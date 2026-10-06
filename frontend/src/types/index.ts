export type UserRole = 'engineer' | 'admin' | 'inspector';

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  title: string;
  department: string;
}

// ─────────────────────────────────────────────────────────────
// Tool life (RUL) — แบบจำลองอนุกรมเวลาตัวเดียวของระบบ
// ─────────────────────────────────────────────────────────────
export type WearState = 'STEADY' | 'ACCELERATED' | 'END_OF_LIFE';
export type Recommendation = 'OK' | 'WATCH' | 'PLAN_REPLACEMENT' | 'REPLACE_NOW';
export type StreamState = 'IDLE' | 'CUTTING' | 'PAUSED' | 'HOLD' | 'COMPLETED' | 'ERROR';
export type Phase = 'BREAK_IN' | 'BASELINE' | 'MONITOR';
export type StreamConnectionStatus = 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED';

export interface RulPrediction {
  rul_min: number;
  rul_lo: number;
  rul_hi: number;
  rul_accel_min: number;
  t_eol_est: number;
  wear_state: WearState;
  recommendation: Recommendation;
  life_used_pct: number;
  eta_utc: string | null;
  model_version: string;
  at_run: number;
  wall_s_per_cut_min: number; // วินาทีนาฬิกาต่อ 1 นาทีของเวลาตัด (วัดจากสตรีม)
}

export interface StreamEvent {
  at: string;
  level: 'INFO' | 'WARNING' | 'CRITICAL';
  message: string;
  machine: number | null;
}

export interface MachineSnapshot {
  machine: number;
  machine_id: string;
  feed_drive: string;
  tool: number;
  tool_id: string;
  state: StreamState;
  speed: number;
  run_index: number;
  current: { run: number | null; run_index: number; t_min: number; recorded: boolean } | null;
  phase: Phase;
  t_min: number | null;
  prediction: RulPrediction | null;
  baseline_runs: number | null;
  flagged_runs: number;
  input_z_max: number | null;
  started_at: string | null;
  completed: { reason: string; at: string; t_min: number; by?: string } | null;
  cycle_id: string | null; // 1 รอบการใช้งานดอก (ติดตั้ง → ถอด) — เชื่อมกับงานตรวจใบมีด
  inspection: { id: string; ai_verdict: ToolVerdict; status: string } | null;
  installed: { at: string; by: string; req_no: string } | null; // ติดตั้งดอกใหม่ตามใบเบิกแล้ว รอผู้ควบคุมกดเริ่มตัด
  model_ready: boolean;
  events: StreamEvent[];
  history?: RunRecord[];
}

export interface RunRecord {
  run: number;
  run_index: number;
  t_min: number;
  phase: Phase;
  flagged: string[];
  raw: Record<string, number>;
  rel: Record<string, number> | null;
  x_pos: number;
  axis_kind: 'torque' | 'force';
  baseline_runs?: number | null;
  rul: number | null;
  rul_lo?: number;
  rul_hi?: number;
  rul_acc?: number;
  raw_rul?: number;
  T_eol?: number;
  state?: WearState;
  recommendation?: Recommendation;
  input_z_max?: number;
  model_version?: string;
  blocked?: string;
}

export interface FleetSnapshot {
  at: string;
  error: string | null;
  model: { status: string; version: string | null; error: string | null };
  hold_on_replace: boolean;
  speeds: number[];
  machines: MachineSnapshot[];
}

export interface WaveFrame {
  type: 'frame';
  machine: number;
  run: number;
  t: number;
  dt: number;
  fx: number[];
  fy: number[];
  fz: number[];
  sp: number[];
  ax: number[];
  ay: number[];
  y: number[];
}

export type StreamMessage =
  | ({ type: 'snapshot' } & FleetSnapshot)
  | { type: 'run'; machine: number; record: RunRecord }
  | ({ type: 'event' } & StreamEvent)
  | { type: 'gap'; machine: number; seconds: number }
  | WaveFrame;

export interface ModelInfo {
  status: 'READY' | 'UNAVAILABLE' | 'NOT_LOADED';
  error: string | null;
  loaded_at: string | null;
  source: string | null;
  version: string | null;
  sha256: string | null;
  meta: any;
  evaluation: any;
}

export interface ModelVersion {
  version: string;
  active: boolean;
  files: { name: string; size: number; last_modified: string | null }[];
  created_utc?: string;
  train_tools?: number[];
  held_out?: number[];
  variant?: string;
  error?: string;
}

export interface ToolEvaluation {
  machine: number;
  tool: number;
  reason: string;
  completed_at: string;
  model_version: string | null;
  t_removed_min: number;
  vb_at_removal_um: number | null;
  T_accel_true_min: number | null;
  T_eol_true_min: number | null;
  n_predictions: number;
  mae_min?: number;
  mae_last20_min?: number;
  bias_min?: number;
  late_pct?: number;
  coverage_p10_p90_pct?: number;
  first_plan_min?: number | null;
  plan_lead_min?: number | null;
  first_replace_now_min?: number | null;
  replace_margin_min?: number | null;
  replace_late?: boolean;
  accel_alarm_error_min?: number | null;
  life_used_at_replace_pct?: number | null;
  trajectory?: { t_min: number; rul: number; lo: number; hi: number; rul_true: number }[];
  vb_measured?: { t_min: number; vb: number }[];
}

export interface ToolLifeSummary {
  completedTools: number;
  replacedByOperator: number;
  lateReplacements: number;
  meanAbsRulErrorMin: number | null;
  meanRulErrorLast20Min: number | null;
  meanLifeUsedAtReplacePct: number | null;
  meanPlanLeadMin: number | null;
  meanCoverageP10P90Pct: number | null;
  evaluations: ToolEvaluation[];
}

// ─────────────────────────────────────────────────────────────
// Governance
// ─────────────────────────────────────────────────────────────
export interface AuditEvent {
  id: string;
  timestamp: string;
  eventType: string;
  actor: string;
  role: string;
  targetResource: string;
  summary: string;
  status: 'SUCCESS' | 'WARNING' | 'FAILED';
}

// ─────────────────────────────────────────────────────────────
// Tool vision — วัดรอยสึก VB ของใบมีด 4 ใบ/ดอกจากภาพ
// ─────────────────────────────────────────────────────────────
/** โซนตามเกณฑ์ VB (เดียวกับแบบจำลอง RUL): normal < 103 µm ≤ accel < 140 µm ≤ eol */
export type VbZone = 'normal' | 'accel' | 'eol';
export type VbSource = 'AI' | 'MANUAL';
export type ToolVerdict = 'OK' | 'MONITOR' | 'REPLACE';

export interface VisionBlade {
  id: string;
  blade: number;
  pred_vb: number | null; // VB ที่ AI วัด (µm)
  vb_lo: number | null; // ช่วง P10–P90
  vb_hi: number | null;
  zone: VbZone;
  confidence: number; // ความน่าจะเป็นของโซนที่ทาย
  probs: Record<VbZone, number>;
  near_threshold: boolean; // ช่วง P10–P90 คร่อมเกณฑ์ 103/140 µm → ควรวัดยืนยัน
  review: 'PENDING' | 'CONFIRMED' | 'MEASURED';
  final_vb: number | null;
  vb_source: VbSource | null;
  final_zone: VbZone | null;
  trained_in_version: string | null;
  image_url: string;
}

/** สิ่งที่ Machine Monitoring (แบบจำลอง RUL) บอก ณ ตอนถอดดอก — ไม่มี VB จริง */
export interface RulContext {
  machine: number;
  machine_id: string;
  tool: number;
  tool_id: string;
  cycle_id: string;
  started_at: string | null;
  removed_at: string;
  reason: 'REPLACED_BY_OPERATOR' | 'DATASET_END';
  removed_by: string;
  t_min: number | null;
  rul_min: number | null;
  rul_lo: number | null;
  rul_hi: number | null;
  wear_state: WearState | null;
  recommendation: Recommendation | null;
  first_plan_min: number | null;
  first_replace_now_min: number | null;
  model_version: string | null;
  images_trained_in: string[] | null; // ภาพชุดนี้เคยใช้ retrain แล้ว (ดอกเดิมถูกเล่นซ้ำ)
}

/** ระดับดอก = VB เฉลี่ย 4 ใบ (นิยามเดียวกับ label ของ RUL) */
export interface ToolSummary {
  mean_vb: number;
  mean_lo: number;
  mean_hi: number;
  zone: VbZone;
  verdict: ToolVerdict;
  probs?: Record<VbZone, number>;
  worst_blade: number;
  worst_vb: number;
  over_limit: number[]; // ใบที่เกิน 140 µm เฉพาะใบ
}

export interface ToolFinalSummary {
  mean_vb: number;
  verdict: ToolVerdict;
  worst_blade: number;
  worst_vb: number;
  over_limit: number[];
}

export interface VisionInspection {
  id: string;
  machine: number;
  machine_id: string;
  seq: number;
  source: 'BENCH_DATASET';
  tool_ref: string | null;
  image_tool: string | null;
  cycle_id: string | null;
  rul_context: RulContext | null;
  trigger: string;
  captured_by: string;
  captured_at: string;
  model_version: string;
  ai_verdict: ToolVerdict;
  status: 'PENDING_REVIEW' | 'VERIFIED' | 'ARCHIVED';
  final_verdict: ToolVerdict | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  note: string | null;
  requisition: RequisitionBrief | null; // ใบเบิกดอกทดแทน (ออกเมื่อยืนยันผล)
  blades?: VisionBlade[];
  ai_summary?: ToolSummary | null; // ระดับดอกจากค่า AI (เฉลี่ย 4 ใบ + P10–P90)
  final_summary?: ToolFinalSummary | null; // ระดับดอกจากค่าที่ผู้ตรวจยืนยัน/วัด
  low_confidence?: boolean; // ช่วงของค่าเฉลี่ยระดับดอกคร่อมเกณฑ์
}

export interface VisionStation {
  machine: number;
  machine_id: string;
  tool_id: string | null;
  image_tool: string;
  rul: {
    state: StreamState | null;
    t_min: number | null;
    rul_min: number | null;
    rul_lo: number | null;
    recommendation: Recommendation | null;
    wear_state: WearState | null;
    life_used_pct: number | null;
    completed: MachineSnapshot['completed'];
  } | null;
  cycle_id: string | null;
  cycle_inspection: VisionInspection | null; // ผลตรวจของดอกที่เพิ่งถอดในรอบนี้
  can_capture: boolean;
  pending_review: number;
  open_requisitions: number; // ใบเบิกที่ยังไม่ติดตั้ง
  last: VisionInspection | null;
}

/** ใบเบิกดอกทดแทน: OPEN = รอเบิก → ISSUED = รับดอกจากคลังแล้ว → INSTALLED = ติดตั้งบนเครื่องแล้ว */
export type RequisitionStatus = 'OPEN' | 'ISSUED' | 'INSTALLED';

export interface RequisitionBrief {
  req_no: string;
  status: RequisitionStatus;
  created_at: string | null;
  issued_by: string | null;
  issued_at: string | null;
  installed_by: string | null;
  installed_at: string | null;
}

/** ใบเบิก 1 ใบ = การถอดดอก 1 ครั้ง (หน้าเว็บสร้าง PDF จากข้อมูลนี้) */
export interface Requisition extends RequisitionBrief {
  inspection_id: string;
  machine: number;
  machine_id: string;
  tool_ref: string | null;
  cycle_id: string | null;
  requested_by: string | null;
  verdict: ToolVerdict | null;
  disposition: string | null; // การจัดการดอกที่ถอด ตาม VB เฉลี่ย 4 ใบ
  mean_vb: number | null;
  worst_blade: number | null;
  worst_vb: number | null;
  over_limit: number[];
  blades: { blade: number; final_vb: number | null; vb_source: VbSource | null; pred_vb: number | null; zone: VbZone | null; image_url: string }[];
  removed_t_min: number | null;
  removed_by: string | null;
  removed_at: string | null;
  removal_reason: string | null;
  rul_recommendation: Recommendation | null;
  rul_model_version: string | null;
  vision_model_version: string;
  captured_at: string;
  reviewed_at: string | null;
  note: string | null;
}

export interface Requisitions {
  open: Requisition[];
  done: Requisition[];
}

export interface VisionStats {
  inspections: number;
  pending_review: number;
  reviewed_blades: number;
  measured_blades: number;
  accepted_blades: number;
  mae_um: number | null; // AI เทียบค่าที่วัดจริง
  bias_um: number | null;
  zone_agreement_pct: number | null;
  confusion_measured_vs_ai: Record<VbZone, Record<VbZone, number>>;
}

export interface TrainingPool {
  n_labels: number; // ค่า VB ที่วัดจริงและยังไม่เคยใช้ฝึก (ใบ)
  n_tools: number; // จำนวนดอกของค่าเหล่านั้น
  n_new_tools: number; // ดอกที่ยังไม่เคยถูกลองฝึก — ครบ min_new_tools แล้ว retrain เริ่มเอง
  min_new_tools: number;
  n_large_error: number;
  large_error_um: number;
  job_running: boolean;
  awaiting_decision: boolean; // มี candidate รอ promote / reject → ยังไม่เริ่มรอบใหม่
}

export interface EvalBrief {
  n: number;
  mae?: number;
  rmse?: number;
  zone_acc?: number;
}

/** 1 epoch ของการฝึก (loss เป็นหน่วย Huber บน VB/100, val_mae เป็น µm) */
export interface TrainEpoch {
  epoch: number;
  member?: number;            // สมาชิกของ ensemble (epoch นับต่อกันข้ามสมาชิก)
  train_loss: number;
  val_loss?: number;
  val_mae?: number;
  lr?: number;
}

export interface TrainingJob {
  id: string;
  status: 'QUEUED' | 'RUNNING' | 'DONE' | 'FAILED' | 'PROMOTED' | 'REJECTED';
  requested_by: string;
  requested_at: string;
  finished_at: string | null;
  base_version: string;
  candidate_version: string | null;
  n_labels: number;
  n_large_error: number;
  result: {
    candidate_version: string;
    gate: { passed: boolean; no_regression_on_val: boolean; not_worse_on_recent: boolean; rule: string };
    metrics: { val: EvalBrief; base_val: EvalBrief; recent: EvalBrief; base_recent: EvalBrief };
    n_human_train: number;
    n_recent_eval: number;
    history?: TrainEpoch[];
  } | null;
  error: string | null;
  progress?: {
    stage: 'training' | 'evaluating' | 'done';
    epoch: number;
    epochs: number;              // รวมทุกสมาชิก (ใช้กับแถบความคืบหน้า)
    epochs_per_member?: number;  // ใช้กับแกนของกราฟ
    members?: number;
    history: TrainEpoch[];
  } | null;
}

export interface VisionModelInfo {
  status: 'READY' | 'UNAVAILABLE' | 'NOT_LOADED';
  error: string | null;
  loaded_at: string | null;
  version: string | null;
  sha256: string | null;
  meta: any;
}

export interface VisionVersion {
  version: string;
  active: boolean;
  status: string;
  task: string;
  created_utc: string;
  base_version: string | null;
  n_human_labels: number | null;
  val_mae: number | null;
  test_mae: number | null;
  gate: any;
  arch?: string | null;
  epochs?: number | null;
  history?: TrainEpoch[] | null;
}
