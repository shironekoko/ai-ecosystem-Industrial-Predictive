export type UserRole = 'engineer' | 'admin' | 'inspector';

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  title: string;
  department: string;
}

export type ToolConditionState = 'SHARP' | 'USED' | 'DULLED';

export interface CNCSpindleAsset {
  id: string;
  name: string;
  line: string;
  toolId: number; // e.g., 10
  currentRun: number; // e.g., 1 to 14
  currentBlade: number; // 1 to 4
  flankWearUm: number; // Flank Wear in micrometers
  gapsUm: number;
  overhangUm: number;
  rulCuts: number;
  healthIndex: number;
  status: 'HEALTHY' | 'WARNING' | 'CRITICAL';
  cuttingSpeedRpm: number;
  feedRateMmpm: number;
  avgForceN: number;
}

export interface ForceTelemetryPoint {
  timeMs: number;
  fx: number;
  fy: number;
  fz: number;
  resultantForce: number;
}

export type StreamConnectionStatus = 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED' | 'EMULATING';

export interface TelemetryPacket {
  timestamp: number;
  passIndex: number;
  cycleDurationSec: number;
  samplingRateHz: number;
  forces: {
    fx: number;
    fy: number;
    fz: number;
    fres: number;
  };
  waveformChunk: {
    fx: number[];
    fy: number[];
    fz: number[];
  };
  inference: {
    condition: ToolConditionState;
    confidence: number;
    flankWearUm: number; // ISO 8688 In-Process Vb Soft Sensor Estimate
    chippingGapUm: number; // Micro-chipping / Gap Estimate
    estimatedRemainingCycles: number | null; // Dynamic RUL
  };
  interlockStatus: 'NORMAL' | 'WARNING' | 'TRIPPED';
  interlockReason?: string;
  machineState: 'ENGAGED' | 'RETRACTING' | 'IDLE' | 'EMERGENCY_HALTED';
}

export interface VerificationRecord {
  id: string; // e.g., T10R12B1
  toolId: number;
  runIndex: number;
  bladeIndex: number;
  sensorPrediction: ToolConditionState;
  sensorConfidence: number;
  visionPrediction: ToolConditionState;
  visionConfidence: number;
  flankWearMeasuredUm: number;
  gapsUm: number;
  overhangUm: number;
  imageUrl: string;
  hasGradCam: boolean;
  status: 'PENDING_VERIFICATION' | 'CONFIRMED_WEAR' | 'FALSE_ALARM';
  verifiedBy?: string;
  verifiedAt?: string;
  notes?: string;
}

export interface ModelRegistryItem {
  id: string;
  name: string;
  architecture: '1D-CNN + BiLSTM' | 'YOLOv8-cls (Transfer Learning)' | 'ResNet34';
  modality: 'Time-Series (Forces Fx,Fy,Fz)' | 'Non-Time-Series (Tool Images)';
  version: string;
  accuracy: number;
  f1Score: number;
  valLoss: number;
  parametersCount: string;
  status: 'PRODUCTION' | 'STAGING' | 'ARCHIVED';
  lastTrainedAt: string;
  datasetTrainedOn: string;
}

export interface ActiveLearningPoolItem {
  id: string;
  sampleId: string;
  source: 'HUMAN_CONFIRMED' | 'HIGH_UNCERTAINTY' | 'DISAGREEMENT';
  modality: 'FORCE_SIGNAL' | 'TOOL_IMAGE';
  confirmedLabel: ToolConditionState;
  addedAt: string;
  notes: string;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  eventType: 'WEAR_CONFIRMED' | 'FALSE_ALARM_FLAGGED' | 'RETRAIN_TRIGGERED' | 'MODEL_PROMOTED' | 'USER_ACCESS';
  actor: string;
  role: string;
  targetResource: string;
  summary: string;
  status: 'SUCCESS' | 'WARNING' | 'FAILED';
}

export interface AlertNotification {
  id: string;
  severity: 'CRITICAL' | 'WARNING' | 'INFO';
  sourceService: 'Force_BiLSTM_Worker' | 'Vision_YOLO_Worker' | 'Redis_Broker' | 'System_Core';
  title: string;
  message: string;
  timestamp: string;
  isRead: boolean;
  toolRef?: string; // e.g. "T10R12B2"
  actionUrl?: string; // e.g. "/visual-qc?id=T10R12B2"
}

export type MachineAsset = CNCSpindleAsset;

