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
  n_runs: number;
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

export interface AlertNotification {
  id: string;
  severity: 'CRITICAL' | 'WARNING' | 'INFO';
  sourceService: string;
  title: string;
  message: string;
  timestamp: string;
  isRead: boolean;
  toolRef?: string;
  actionUrl?: string;
}

// ─────────────────────────────────────────────────────────────
// Tool vision — ตรวจใบมีด 4 ใบ/เครื่องด้วยภาพ
// ─────────────────────────────────────────────────────────────
export type BladeLabel = 'sharp' | 'used' | 'dulled';
export type ToolVerdict = 'OK' | 'MONITOR' | 'REPLACE';

export interface VisionBlade {
  id: string;
  blade: number;
  pred_label: BladeLabel;
  confidence: number;
  probs: Record<BladeLabel, number>;
  metrology: { flank_wear_um: number; gaps_um: number; overhang_um: number } | null;
  review: 'PENDING' | 'CONFIRMED' | 'CORRECTED';
  final_label: BladeLabel | null;
  replace_status: 'NONE' | 'REQUIRED' | 'REPLACED';
  replaced_by: string | null;
  replaced_at: string | null;
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
  blades?: VisionBlade[];
  low_confidence?: boolean;
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
  open_replacements: number;
  last: VisionInspection | null;
}

export interface ReplacementItem {
  blade_id: string;
  inspection_id: string;
  machine: number;
  machine_id: string;
  blade: number;
  tool_ref: string | null;
  removed_t_min: number | null;
  removed_by: string | null;
  rul_recommendation: Recommendation | null;
  captured_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  ai_label: BladeLabel;
  final_label: BladeLabel;
  ai_correct: boolean;
  flank_wear_um: number | null;
  status: 'REQUIRED' | 'REPLACED';
  replaced_by: string | null;
  replaced_at: string | null;
  image_url: string;
}

export interface Replacements {
  open: ReplacementItem[];
  done: ReplacementItem[];
  summary: { inspection_id: string; machine_id: string; tool_ref: string | null; removed_t_min: number | null; reviewed_by: string | null; blades: string[] }[];
}

export interface VisionStats {
  inspections: number;
  pending_review: number;
  reviewed_blades: number;
  agreement_pct: number | null;
  corrected: number;
  confusion_human_vs_ai: Record<BladeLabel, Record<BladeLabel, number>>;
}

export interface TrainingPool {
  n_labels: number;
  n_corrected: number;
  n_confirmed: number;
  suggest_retrain: boolean;
  threshold: number;
  job_running: boolean;
}

export interface EvalBrief {
  n: number;
  accuracy?: number;
  macro_f1?: number;
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
  n_corrected: number;
  result: {
    candidate_version: string;
    gate: { passed: boolean; no_regression_on_val: boolean; not_worse_on_recent: boolean; rule: string };
    metrics: { val: EvalBrief; base_val: EvalBrief; recent: EvalBrief; base_recent: EvalBrief };
    n_human_train: number;
    n_recent_eval: number;
  } | null;
  error: string | null;
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
  created_utc: string;
  base_version: string | null;
  n_human_labels: number | null;
  metrics: any;
  gate: any;
}
