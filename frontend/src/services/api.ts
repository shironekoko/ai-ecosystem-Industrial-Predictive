/**
 * API Service Client for Nonastreda CNC Tool Wear AI Platform
 * Connects to FastAPI Backend (/api/v1) for real-time edge telemetry and QC verification.
 */

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api/v1';

export interface ApiStatus {
  online: boolean;
  gateway: string;
  latencyMs?: number;
}

export interface ForcePredictionResult {
  toolCondition: 'SHARP' | 'USED' | 'DULLED';
  confidence: number;
  flankWearEstimateUm: number;
  rulCuts: number;
  resultantForceN: number;
}

export interface ImagePredictionResult {
  class: 'SHARP' | 'USED' | 'DULLED';
  confidence: number;
  conditionDescription: string;
  gradCamAvailable: boolean;
}

export interface BladeQCData {
  recordId: string;
  imageUrl: string;
  chipImageUrl: string;
  toolImageUrl: string;
  toolProcessedImageUrl: string;
  gradCamUrl?: string | null;
  tier1ForceAlert: {
    condition: 'SHARP' | 'USED' | 'DULLED';
    confidence: number;
    flankWearEstimateUm: number;
    triggerMetric: string;
    status: 'NORMAL' | 'WARNING' | 'ALERT';
  };
  tier2ChipAi: {
    condition: 'SHARP' | 'USED' | 'DULLED';
    confidence: number;
    chipImageUrl: string;
    morphologyAnalysis: string;
    curlContinuity: 'CONTINUOUS' | 'SEGMENTED' | 'DISCONTINUOUS_BRITTLE';
    surfaceRoughnessIndex: number;
  };
  tier3ToolEdge: {
    toolImageUrl: string;
    processedImageUrl: string;
    flankWearUm: number;
    gapsUm: number;
    overhangUm: number;
    chippingDetected: boolean;
    isoLimitExceeded: boolean;
    edgeIntegrityScore: number;
    opticalVerdict: 'SHARP' | 'USED' | 'DULLED';
  };
  consensus: {
    isAgreement: boolean;
    discrepancyType: 'NONE' | 'CHIP_FALSE_ALARM' | 'CHIP_UNDERPREDICTED';
    consensusVerdict: 'CONFIRMED_WEAR' | 'DISCREPANCY_FLAGGED' | 'CUTTER_NORMAL';
    recommendedAction: 'REPLACE_TOOL' | 'SEND_TO_RETRAIN' | 'CONTINUE_CUTTING';
    rationale: string;
  };
  visionPrediction: 'SHARP' | 'USED' | 'DULLED';
  visionConfidence: number;
  flankWearUm: number;
  gapsUm: number;
  overhangUm: number;
  status: 'PENDING_VERIFICATION' | 'CONFIRMED_WEAR' | 'FALSE_ALARM' | 'RETRAIN_FLAGGED';
  verifiedBy?: string | null;
  verifiedAt?: string | null;
}

export interface QCTargetData {
  toolId?: number;
  passIndex?: number;
  teethCount?: number;
  originSpindle?: string;
  dispatchReason?: string;
  dispatchedAt?: string;
}

export class ApiService {
  private static instance: ApiService;
  private isBackendOnline: boolean = false;

  public getAuthHeaders(): Record<string, string> {
    const token = localStorage.getItem('pdm_access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  private constructor() {
    this.checkHealth();
  }

  public static getInstance(): ApiService {
    if (!ApiService.instance) {
      ApiService.instance = new ApiService();
    }
    return ApiService.instance;
  }

  /**
   * Check connection to backend FastAPI server
   */
  public async checkHealth(): Promise<ApiStatus> {
    const startTime = performance.now();
    try {
      const response = await fetch(`${API_BASE_URL}/health`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      const latency = Math.round(performance.now() - startTime);
      this.isBackendOnline = response.ok;
      return {
        online: response.ok,
        gateway: API_BASE_URL,
        latencyMs: latency,
      };
    } catch {
      this.isBackendOnline = false;
      return {
        online: false,
        gateway: API_BASE_URL,
      };
    }
  }

  public get online(): boolean {
    return this.isBackendOnline;
  }

  /**
   * Fetch spindle cutting forces telemetry
   */
  public async getForces(toolId: number, runIndex: number) {
    try {
      const res = await fetch(`${API_BASE_URL}/telemetry/forces?tool_id=${toolId}&run=${runIndex}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend telemetry error:', err);
    }
    return null;
  }

  public async getRunWaveform(toolId: number = 10, run: number = 1) {
    try {
      const res = await fetch(`${API_BASE_URL}/telemetry/waveform?tool_id=${toolId}&run=${run}&points=60`);
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend getRunWaveform error:', err);
    }
    return [];
  }


  /**
   * Run Pure Time-Series CRNN Inference on force dynamics
   */
  public async predictForces(forcesChunk: { fx: number[]; fy: number[]; fz: number[] }): Promise<ForcePredictionResult | null> {
    try {
      const res = await fetch(`${API_BASE_URL}/inference/predict-forces`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(forcesChunk),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend inference error:', err);
    }
    return null;
  }

  /**
   * Get Registered Models from MLflow Registry via backend API
   */
  public async getRegisteredModels() {
    try {
      const res = await fetch(`${API_BASE_URL}/models/registry`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          return data;
        }
      }
    } catch (err) {
      console.warn('[API] Backend models registry error:', err);
    }
    return [];
  }

  /**
   * Fetch active QC target dismounted on bench
   */
  public async getQcTarget(tool?: number, run?: number): Promise<QCTargetData | null> {
    try {
      const q = [];
      if (tool !== undefined) q.push(`tool=${tool}`);
      if (run !== undefined) q.push(`run=${run}`);
      const qs = q.length ? `?${q.join('&')}` : '';
      const res = await fetch(`${API_BASE_URL}/qc/target${qs}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend getQcTarget error:', err);
    }
    return null;
  }

  /**
   * Fetch 3-Tier Multi-Modal QC inspection data for a specific blade
   */
  public async getBladeQc(toolId: number, runIndex: number, bladeIndex: number): Promise<BladeQCData | null> {
    try {
      const res = await fetch(`${API_BASE_URL}/qc/tools/${toolId}/runs/${runIndex}/blades/${bladeIndex}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend getBladeQc error:', err);
    }
    return null;
  }

  /**
   * Submit Human-in-the-Loop Verification Sign-off to backend API
   */
  public async submitVerification(
    recordId: string,
    toolId: number,
    passIndex: number,
    bladeIndex: number,
    decision: 'CONFIRMED_WEAR' | 'FALSE_ALARM' | 'SEND_TO_RETRAIN',
    notes?: string,
    inspectorName?: string,
    actualCondition?: 'SHARP' | 'USED' | 'DULLED'
  ) {
    try {
      const res = await fetch(`${API_BASE_URL}/qc/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...this.getAuthHeaders() },
        body: JSON.stringify({
          recordId: recordId,
          toolId: toolId,
          passIndex: passIndex,
          bladeIndex: bladeIndex,
          decision: decision,
          actualCondition: actualCondition,
          notes: notes || '',
          inspectorName: inspectorName || 'Maintenance Engineer',
        }),
      });
      if (!res.ok) {
        throw new Error(`Failed to submit verification: ${res.statusText}`);
      }
      return await res.json();
    } catch (err) {
      console.warn('[API] Backend verify submission error:', err);
      throw err;
    }
  }

  /**
   * Enqueue Model Retraining Job to Redis / ARQ Worker via backend Retrain API
   */
  public async triggerRetrain(
    modelName: string = 'Pure_Time_Series_CRNN_NoTool4',
    datasetName: string = 'forces',
    options?: { modelType?: string; epochs?: number; batchSize?: number }
  ) {
    const res = await fetch(`${API_BASE_URL}/retrain/trigger`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model_name: modelName,
        dataset_name: datasetName,
        model_type: options?.modelType || 'timeseries',
        epochs: options?.epochs || 10,
        batch_size: options?.batchSize || 16,
      }),
    });
    if (!res.ok) {
      throw new Error(`Failed to enqueue retraining: ${res.statusText}`);
    }
    return await res.json();
  }

  public async enqueueTraining(
    modelName: string = 'yolov8_chip_wear',
    datasetName: string = 'chip',
    options?: { modelType?: string; epochs?: number; batchSize?: number }
  ) {
    return this.triggerRetrain(modelName, datasetName, options);
  }

  /**
   * Check Retraining Job Status from ARQ Worker via backend Retrain API
   */
  public async getRetrainStatus(jobId: string) {
    const res = await fetch(`${API_BASE_URL}/retrain/status/${jobId}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch retraining status: ${res.statusText}`);
    }
    return await res.json();
  }

  public async getTrainingStatus(jobId: string) {
    return this.getRetrainStatus(jobId);
  }

  public async getRetrainQueueCount(): Promise<number> {
    try {
      const res = await fetch(`${API_BASE_URL}/retrain/queue-count`);
      if (res.ok) {
        const data = await res.json();
        return typeof data.queueCount === 'number' ? data.queueCount : 0;
      }
    } catch (err) {
      console.warn('[API] Backend getRetrainQueueCount error:', err);
    }
    return 0;
  }

  public async pingWorker(): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE_URL}/workers/redis/ping`);
      return res.ok;
    } catch {
      return false;
    }
  }

  /**
   * Fetch CNC spindle fleet status
   */
  public async getFleetSpindles() {
    try {
      const res = await fetch(`${API_BASE_URL}/fleet/spindles?_t=${Date.now()}`, {
        cache: 'no-store',
        headers: {
          ...this.getAuthHeaders(),
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          Pragma: 'no-cache',
        },
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend getFleetSpindles error:', err);
    }
    return [];
  }

  /**
   * Fetch fleet health summary
   */
  public async getFleetSummary() {
    try {
      const res = await fetch(`${API_BASE_URL}/fleet/summary?_t=${Date.now()}`, {
        cache: 'no-store',
        headers: {
          ...this.getAuthHeaders(),
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          Pragma: 'no-cache',
        },
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend getFleetSummary error:', err);
    }
    return null;
  }

  /**
   * Fetch audit logs from backend
   */
  public async getAuditLogs(eventType?: string, search?: string, page: number = 1, limit: number = 50) {
    try {
      const params = new URLSearchParams();
      if (eventType && eventType !== 'ALL') params.append('eventType', eventType);
      if (search && search.trim()) params.append('search', search.trim());
      params.append('page', String(page));
      params.append('limit', String(limit));

      const res = await fetch(`${API_BASE_URL}/audit-logs?${params.toString()}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend getAuditLogs error:', err);
    }
    return { items: [], total: 0, page: 1, limit: 50 };
  }

  /**
   * Fetch degradation & reliability reports summary
   */
  public async getDegradationSummary(period: string = '30D') {
    try {
      const res = await fetch(`${API_BASE_URL}/reports/degradation-summary?period=${encodeURIComponent(period)}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend getDegradationSummary error:', err);
    }
    return null;
  }

  /**
   * Fetch alarms & notifications
   */
  public async getAlarms(severity: string = 'ALL', isRead?: boolean) {
    try {
      const params = new URLSearchParams();
      if (severity && severity !== 'ALL') params.append('severity', severity);
      if (isRead !== undefined) params.append('is_read', String(isRead));

      const qs = params.toString() ? `?${params.toString()}` : '';
      const res = await fetch(`${API_BASE_URL}/alarms${qs}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend getAlarms error:', err);
    }
    return [];
  }

  public async markAlarmRead(alarmId: string) {
    try {
      const res = await fetch(`${API_BASE_URL}/alarms/${alarmId}/read`, { method: 'PATCH' });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend markAlarmRead error:', err);
    }
    return null;
  }

  public async markAllAlarmsRead() {
    try {
      const res = await fetch(`${API_BASE_URL}/alarms/mark-all-read`, { method: 'POST' });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend markAllAlarmsRead error:', err);
    }
    return { updatedCount: 0 };
  }

  public async deleteAlarm(alarmId: string) {
    try {
      const res = await fetch(`${API_BASE_URL}/alarms/${alarmId}`, { method: 'DELETE' });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend deleteAlarm error:', err);
    }
    return null;
  }

  /**
   * Users Management APIs
   */
  public async getUsers() {
    try {
      const res = await fetch(`${API_BASE_URL}/users`, { headers: { ...this.getAuthHeaders() } });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend getUsers error:', err);
    }
    return [];
  }

  public async createUser(userData: { name: string; email: string; role: string; department?: string; title?: string; password?: string }) {
    try {
      const res = await fetch(`${API_BASE_URL}/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...this.getAuthHeaders() },
        body: JSON.stringify(userData),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend createUser error:', err);
    }
    return null;
  }

  public async updateUserRole(userId: string, role: string) {
    try {
      const res = await fetch(`${API_BASE_URL}/users/${userId}/role`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...this.getAuthHeaders() },
        body: JSON.stringify({ role }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend updateUserRole error:', err);
    }
    return null;
  }

  public async deleteUser(userId: string) {
    try {
      const res = await fetch(`${API_BASE_URL}/users/${userId}`, { method: 'DELETE', headers: { ...this.getAuthHeaders() } });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend deleteUser error:', err);
    }
    return null;
  }

  /**
   * Spindle and Machine Control APIs
   */
  public async controlSpindle(action: 'E_STOP' | 'RESUME' | 'RESET' | 'FEED_HOLD', spindleId: string = 'CNC-SP-01') {
    try {
      const res = await fetch(`${API_BASE_URL}/telemetry/spindle/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...this.getAuthHeaders() },
        body: JSON.stringify({ spindleId, action }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend controlSpindle error:', err);
    }
    return null;
  }

  public async stopMachine(reason: string = 'Operator Emergency Stop', run?: number) {
    try {
      const res = await fetch(`${API_BASE_URL}/telemetry/machine/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...this.getAuthHeaders() },
        body: JSON.stringify({ reason, run }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend stopMachine error:', err);
    }
    return null;
  }

  public async startMachine() {
    try {
      const res = await fetch(`${API_BASE_URL}/telemetry/machine/start`, {
        method: 'POST',
        headers: { ...this.getAuthHeaders() },
      });
      if (res.ok) {
        return await res.json();
      }
      const errData = await res.json().catch(() => ({}));
      return { success: false, detail: errData.detail || 'Start machine failed' };
    } catch (err) {
      console.warn('[API] Backend startMachine error:', err);
      return { success: false, detail: String(err) };
    }
  }

  public async pauseMachine(reason: string = 'Operator paused cutting stream') {
    try {
      const res = await fetch(`${API_BASE_URL}/telemetry/machine/pause`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...this.getAuthHeaders() },
        body: JSON.stringify({ reason }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend pauseMachine error:', err);
    }
    return null;
  }

  public async resetMachine() {
    try {
      const res = await fetch(`${API_BASE_URL}/telemetry/machine/reset`, {
        method: 'POST',
        headers: { ...this.getAuthHeaders() },
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend resetMachine error:', err);
    }
    return null;
  }

  public async getMachineStatus() {
    try {
      const res = await fetch(`${API_BASE_URL}/telemetry/machine/status?_t=${Date.now()}`, {
        cache: 'no-store',
        headers: {
          ...this.getAuthHeaders(),
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          Pragma: 'no-cache',
        },
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend getMachineStatus error:', err);
    }
    return null;
  }

  public async getMillingHistory() {
    try {
      const res = await fetch(`${API_BASE_URL}/telemetry/history?_t=${Date.now()}`, {
        cache: 'no-store',
        headers: {
          ...this.getAuthHeaders(),
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          Pragma: 'no-cache',
        },
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend getMillingHistory error:', err);
    }
    return null;
  }

  /** Generic GET helper for flexibility */
  public async get(endpoint: string): Promise<{ data: any }> {
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    const url = endpoint.startsWith('http')
      ? endpoint
      : endpoint.startsWith('/api/v1')
      ? `${API_BASE_URL.replace('/api/v1', '')}${cleanEndpoint}`
      : `${API_BASE_URL}${cleanEndpoint}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const data = await res.json();
    return { data };
  }

  /** Generic POST helper for flexibility */
  public async post(endpoint: string, body?: any): Promise<{ data: any }> {
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    const url = endpoint.startsWith('http')
      ? endpoint
      : endpoint.startsWith('/api/v1')
      ? `${API_BASE_URL.replace('/api/v1', '')}${cleanEndpoint}`
      : `${API_BASE_URL}${cleanEndpoint}`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const data = await res.json();
    return { data };
  }

  /**
   * Real Authentication: Login against PostgreSQL backed backend (/api/v1/auth/login)
   */
  public async login(email: string, password: string): Promise<{ access_token: string; refresh_token: string; user: any }> {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      let detail = 'อีเมลหรือรหัสผ่านไม่ถูกต้อง (Invalid credentials)';
      try {
        const errJson = await res.json();
        if (errJson.detail) detail = errJson.detail;
      } catch {}
      throw new Error(detail);
    }
    return await res.json();
  }

  /**
   * Real Authentication: Register new account in PostgreSQL (/api/v1/auth/signup)
   */
  public async register(userData: {
    email: string;
    password: string;
    name?: string;
    username?: string;
    role?: string;
    department?: string;
    title?: string;
  }): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: userData.email,
        password: userData.password,
        full_name: userData.name || userData.email.split('@')[0],
        username: userData.username || userData.email.split('@')[0],
        role: userData.role || 'engineer',
        department: userData.department || 'Maintenance Team',
        title: userData.title || 'Reliability Engineer',
      }),
    });
    if (!res.ok) {
      let detail = 'Registration failed';
      try {
        const errJson = await res.json();
        if (errJson.detail) detail = errJson.detail;
      } catch {}
      throw new Error(detail);
    }
    return await res.json();
  }

  /**
   * Get Current Authenticated User (/api/v1/auth/me)
   */
  public async getMe(token?: string): Promise<any> {
    const authToken = token || localStorage.getItem('pdm_access_token');
    if (!authToken) return null;
    try {
      const res = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        return await res.json();
      }
    } catch {}
    return null;
  }
}

export const api = ApiService.getInstance();
