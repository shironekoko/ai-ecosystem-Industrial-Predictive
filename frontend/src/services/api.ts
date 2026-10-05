/**
 * API client — FastAPI backend (/api/v1)
 * ระบบมีแบบจำลองอนุกรมเวลาเพียงตัวเดียว: GRU พยากรณ์อายุใช้งานที่เหลือ (RUL) ของดอกกัด
 * แบบจำลองถูกโหลดจาก MinIO โดย backend และข้อมูลไหลจากชุดข้อมูลจริง (LUH) ตามเวลาจริง
 */
import type {
  BenchMeasurement,
  VbSource,
  FleetSnapshot,
  Replacements,
  TrainingJob,
  TrainingPool,
  VisionInspection,
  VisionModelInfo,
  VisionStation,
  VisionStats,
  VisionVersion,
  MachineSnapshot,
  ModelInfo,
  ModelVersion,
  ToolEvaluation,
  ToolLifeSummary,
} from '../types';

export const API_BASE_URL: string = (import.meta as any).env?.VITE_API_URL || '/api/v1';

export interface ApiStatus {
  online: boolean;
  gateway: string;
  latencyMs?: number;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    cache: 'no-store',
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
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

  // ───────────────────────── Tool life (RUL) ─────────────────────────
  public getFleet() {
    return request<FleetSnapshot>('/tool-life/fleet');
  }

  public getMachine(machine: number, history = false) {
    return request<MachineSnapshot>(`/tool-life/machines/${machine}?history=${history}`);
  }

  public controlMachine(machine: number, action: 'start' | 'pause' | 'resume' | 'reset') {
    return request<MachineSnapshot>(`/tool-life/machines/${machine}/${action}`, { method: 'POST' });
  }

  public setSpeed(machine: number, speed: number) {
    return request<MachineSnapshot>(`/tool-life/machines/${machine}/speed`, {
      method: 'POST',
      body: JSON.stringify({ speed }),
    });
  }

  public acknowledge(machine: number, action: 'continue' | 'replace', actor: string) {
    return request<MachineSnapshot>(`/tool-life/machines/${machine}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify({ action, actor }),
    });
  }

  public getModel() {
    return request<ModelInfo>('/tool-life/model');
  }

  public getModelVersions() {
    return request<ModelVersion[]>('/tool-life/model/versions');
  }

  public reloadModel(version?: string) {
    return request<ModelInfo>('/tool-life/model/reload', {
      method: 'POST',
      body: JSON.stringify({ version: version ?? null }),
    });
  }

  public getEvaluations(detail = true) {
    return request<ToolEvaluation[]>(`/tool-life/evaluations?detail=${detail}`);
  }

  public getToolLifeSummary() {
    return request<ToolLifeSummary>('/reports/tool-life-summary');
  }

  public exportCsvUrl() {
    return `${API_BASE_URL}/reports/export/csv`;
  }

  // ───────────────────────── Tool vision (ตรวจใบมีดด้วยภาพ) ─────────────────────────
  public getVisionStations() {
    return request<VisionStation[]>('/tool-vision/stations');
  }

  /** สำรองเมื่อถ่ายภาพอัตโนมัติตอนถอดดอกไม่สำเร็จ — ได้เฉพาะดอกที่ถอดแล้ว */
  public captureInspection(machine: number, actor: string) {
    return request<VisionInspection>(`/tool-vision/stations/${machine}/capture`, {
      method: 'POST',
      body: JSON.stringify({ actor }),
    });
  }

  public getInspections(status?: string, machine?: number, limit = 100) {
    const q = new URLSearchParams();
    if (status) q.set('status', status);
    if (machine) q.set('machine', String(machine));
    q.set('limit', String(limit));
    return request<VisionInspection[]>(`/tool-vision/inspections?${q.toString()}`);
  }

  public getInspection(id: string) {
    return request<VisionInspection>(`/tool-vision/inspections/${id}`);
  }

  /** วัดใบมีดบน optical bench — เปิดเผยค่าวัดจริงของใบนั้น */
  public measureBlade(id: string, blade: number, actor: string) {
    return request<BenchMeasurement & { blade: number }>(`/tool-vision/inspections/${id}/blades/${blade}/measure`, {
      method: 'POST',
      body: JSON.stringify({ actor }),
    });
  }

  public reviewInspection(id: string, actor: string, blades: { blade: number; source: VbSource; vb_um?: number | null }[], note?: string) {
    return request<VisionInspection>(`/tool-vision/inspections/${id}/review`, {
      method: 'POST',
      body: JSON.stringify({ actor, blades, note: note || null }),
    });
  }

  public getReplacements() {
    return request<Replacements>('/tool-vision/replacements');
  }

  /** ช่างเปลี่ยน/ลับดอกตามใบสั่งงานแล้ว (ปิดทั้งดอก) */
  public markToolServiced(inspectionId: string, actor: string) {
    return request<{ inspection_id: string; status: string }>(`/tool-vision/replacements/${inspectionId}/done`, {
      method: 'POST',
      body: JSON.stringify({ actor }),
    });
  }

  public replacementsCsvUrl() {
    return `${API_BASE_URL}/tool-vision/replacements/export/csv`;
  }

  public getVisionStats() {
    return request<VisionStats>('/tool-vision/stats');
  }

  public getVisionModel() {
    return request<VisionModelInfo>('/tool-vision/model');
  }

  /** โหลดเวอร์ชันตาม latest.json ใน MinIO ใหม่ */
  public reloadVisionModel() {
    return request<VisionModelInfo>('/tool-vision/model/reload', { method: 'POST' });
  }

  /** ใช้เวอร์ชันที่เลือกเป็นตัวหลัก (ย้อนเวอร์ชันได้) */
  public activateVisionVersion(version: string, actor: string) {
    return request<VisionModelInfo>('/tool-vision/model/activate', {
      method: 'POST',
      body: JSON.stringify({ version, actor }),
    });
  }

  public getVisionVersions() {
    return request<VisionVersion[]>('/tool-vision/model/versions');
  }

  public getTrainingPool() {
    return request<TrainingPool>('/tool-vision/training/pool');
  }

  public getTrainingJobs() {
    return request<TrainingJob[]>('/tool-vision/training/jobs');
  }

  public startRetrain(actor: string) {
    return request<{ job_id: string; n_labels: number }>('/tool-vision/training/start', {
      method: 'POST',
      body: JSON.stringify({ actor }),
    });
  }

  public decideTrainingJob(jobId: string, action: 'promote' | 'reject', actor: string) {
    return request<{ job_id: string; status: string; version: string }>(`/tool-vision/training/jobs/${jobId}/${action}`, {
      method: 'POST',
      body: JSON.stringify({ actor }),
    });
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
