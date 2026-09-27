export type UserRole = 'engineer' | 'admin' | 'inspector';

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  title: string;
  department: string;
}

export interface MachineAsset {
  id: string;
  name: string;
  line: string;
  type: string;
  vibrationRms: number;
  temperatureC: number;
  pressureBar: number;
  rulHours: number;
  healthIndex: number;
  status: 'HEALTHY' | 'WARNING' | 'CRITICAL';
  criticalPart: string;
}

export interface RequisitionRecord {
  id: string;
  assetId: string;
  assetName: string;
  partName: string;
  partSku: string;
  predictedRul: number;
  thresholdHours: number;
  urgency: 'HIGH' | 'MEDIUM' | 'LOW';
  estimatedCost: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  requestedAt: string;
  reviewer?: string;
  notes: string;
}

export interface InspectionRecord {
  id: string;
  partSku: string;
  category: string;
  lotNumber: string;
  anomalyScore: number;
  threshold: number;
  aiVerdict: 'PASS' | 'FAIL';
  defectClass?: string;
  inspectedAt: string;
  hasHeatmap: boolean;
  minioKey: string;
}

export interface DeflexQueueItem {
  id: string;
  partSku: string;
  category: string;
  aiVerdict: string;
  groundTruth: string;
  inspectorNote: string;
  inspectorName: string;
  queuedTimestamp: string;
  status: 'QUEUED' | 'PROCESSING' | 'COMPLETED';
}

export interface PartCatalogItem {
  sku: string;
  name: string;
  category: string;
  specifications: string;
  minioObjectPath: string;
  stockQty: number;
  updatedAt: string;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  eventType: 'REQUISITION_DECISION' | 'QC_OVERRIDE' | 'HOT_RELOAD' | 'THRESHOLD_UPDATE' | 'USER_ACCESS';
  actor: string;
  role: string;
  targetResource: string;
  summary: string;
  status: 'SUCCESS' | 'WARNING' | 'FAILED';
}

export interface AlertNotification {
  id: string;
  severity: 'CRITICAL' | 'WARNING' | 'INFO';
  sourceService: 'BiLSTM_Worker' | 'Vision_Worker' | 'Redis_Broker' | 'System_Core';
  title: string;
  message: string;
  timestamp: string;
  isRead: boolean;
}
