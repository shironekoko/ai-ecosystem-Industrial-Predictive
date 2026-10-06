/**
 * API client — FastAPI backend (/api/v1) · ทุก method ในไฟล์นี้ถูกใช้โดยหน้าเว็บ (endpoint ที่ไม่มีผู้เรียกถูกลบออกจาก backend แล้ว)
 * Tool Life (RUL, GRU) · Tool Vision (วัด VB จากภาพ) · Reports · Alarms · Audit · Users · Auth
 * สตรีมสด (WebSocket) อยู่ที่ telemetryStream.ts
 *
 * ทุก request (ยกเว้น login/signup) ส่ง Authorization: Bearer <token> · 401 = token หมดอายุ/ไม่ถูกต้อง → ล้าง session แล้วไปหน้า login
 * ภาพใบมีดและ CSV โหลดผ่าน fetch เป็น blob (<img src> / <a href> ส่ง header ไม่ได้) — ไม่ใส่ token ใน URL เพราะติด access log
 * ผู้ทำรายการใน audit = ผู้ใช้ของ token (backend ไม่รับ actor จาก body)
 */
import type {
  VbSource,
  FleetSnapshot,
  Requisitions,
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
import { endSession, getToken } from './session';

export const API_BASE_URL: string = (import.meta as any).env?.VITE_API_URL || '/api/v1';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** fetch พร้อม Bearer token — url เต็ม (เช่น image_url จาก backend) · 401 → endSession() */
async function authFetch(url: string, init?: RequestInit): Promise<Response> {
  const token = getToken();
  const res = await fetch(url, {
    cache: 'no-store',
    ...init,
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(init?.headers || {}) },
  });
  if (res.status === 401) endSession();
  return res;
}

const apiFetch = (path: string, init?: RequestInit) => authFetch(`${API_BASE_URL}${path}`, init);

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(path, { ...init, headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) } });
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

/** บันทึก CSV ที่ต้องล็อกอินเป็นไฟล์ */
async function downloadCsv(path: string, filename: string) {
  const res = await apiFetch(path);
  if (!res.ok) throw new ApiError(res.status, `ดาวน์โหลด ${filename} ไม่สำเร็จ (HTTP ${res.status})`);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export class ApiService {
  private static instance: ApiService;

  private constructor() {}

  public static getInstance(): ApiService {
    if (!ApiService.instance) {
      ApiService.instance = new ApiService();
    }
    return ApiService.instance;
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

  public acknowledge(machine: number, action: 'continue' | 'replace') {
    return request<MachineSnapshot>(`/tool-life/machines/${machine}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    });
  }

  public getModel() {
    return request<ModelInfo>('/tool-life/model');
  }

  public getModelVersions() {
    return request<ModelVersion[]>('/tool-life/model/versions');
  }

  /** admin */
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

  public downloadEvaluationsCsv() {
    return downloadCsv('/reports/export/csv', 'tool_life_evaluations.csv');
  }

  // ───────────────────────── Tool vision (ตรวจใบมีดด้วยภาพ) ─────────────────────────
  public getVisionStations() {
    return request<VisionStation[]>('/tool-vision/stations');
  }

  /** สำรองเมื่อถ่ายภาพอัตโนมัติตอนถอดดอกไม่สำเร็จ — ได้เฉพาะดอกที่ถอดแล้ว */
  public captureInspection(machine: number) {
    return request<VisionInspection>(`/tool-vision/stations/${machine}/capture`, { method: 'POST' });
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

  /** ไฟล์ที่ต้องล็อกอินจาก url เต็มที่ backend ส่งมา (เช่น image_url ของใบมีด) — ใช้ผ่าน <AuthImage> */
  public async getBlob(url: string) {
    const res = await authFetch(url);
    if (!res.ok) throw new ApiError(res.status, `HTTP ${res.status}`);
    return res.blob();
  }

  /** ผลวัด VB ของใบมีด (ชุดข้อมูล) — ค่าเริ่มต้นของช่อง "กรอกค่าที่วัด" */
  public getBladeMeasurement(id: string, blade: number) {
    return request<{ blade: number; vb_um: number }>(`/tool-vision/inspections/${id}/blades/${blade}/measurement`);
  }

  public reviewInspection(id: string, blades: { blade: number; source: VbSource; vb_um?: number | null }[], note?: string) {
    return request<VisionInspection>(`/tool-vision/inspections/${id}/review`, {
      method: 'POST',
      body: JSON.stringify({ blades, note: note || null }),
    });
  }

  public getRequisitions() {
    return request<Requisitions>('/tool-vision/requisitions');
  }

  /** รับดอกทดแทนจากคลังเครื่องมือแล้ว */
  public issueRequisition(inspectionId: string) {
    return request<{ req_no: string; status: string }>(`/tool-vision/requisitions/${inspectionId}/issue`, { method: 'POST' });
  }

  /** ติดตั้งดอกใหม่บนเครื่องแล้ว → เครื่องเริ่มรอบใหม่ในสถานะหยุดชั่วคราว (machine_ready) */
  public installRequisition(inspectionId: string) {
    return request<{ req_no: string; status: string; machine: number; machine_ready: boolean }>(
      `/tool-vision/requisitions/${inspectionId}/install`,
      { method: 'POST' },
    );
  }

  public downloadRequisitionsCsv() {
    return downloadCsv('/tool-vision/requisitions/export/csv', 'tool_requisitions.csv');
  }

  public getVisionStats() {
    return request<VisionStats>('/tool-vision/stats');
  }

  public getVisionModel() {
    return request<VisionModelInfo>('/tool-vision/model');
  }

  /** โหลดเวอร์ชันตาม latest.json ใน MinIO ใหม่ (admin) */
  public reloadVisionModel() {
    return request<VisionModelInfo>('/tool-vision/model/reload', { method: 'POST' });
  }

  /** ใช้เวอร์ชันที่เลือกเป็นตัวหลัก (ย้อนเวอร์ชันได้, admin) */
  public activateVisionVersion(version: string) {
    return request<VisionModelInfo>('/tool-vision/model/activate', {
      method: 'POST',
      body: JSON.stringify({ version }),
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

  /** admin */
  public decideTrainingJob(jobId: string, action: 'promote' | 'reject') {
    return request<{ job_id: string; status: string; version: string }>(`/tool-vision/training/jobs/${jobId}/${action}`, { method: 'POST' });
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

      const res = await apiFetch(`/audit-logs?${params.toString()}`);
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
      const res = await apiFetch(`/alarms${qs}`);
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
      const res = await apiFetch(`/alarms/${alarmId}/read`, { method: 'PATCH' });
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
      const res = await apiFetch('/alarms/mark-all-read', { method: 'POST' });
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
      const res = await apiFetch(`/alarms/${alarmId}`, { method: 'DELETE' });
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
      const res = await apiFetch('/users');
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
      const res = await apiFetch('/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
      const res = await apiFetch(`/users/${userId}/role`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
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
      const res = await apiFetch(`/users/${userId}`, { method: 'DELETE' });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[API] Backend deleteUser error:', err);
    }
    return null;
  }

  /**
   * Real Authentication: Login against PostgreSQL backed backend (/api/v1/auth/login)
   * fetch ตรง (ไม่ผ่าน apiFetch): รหัสผ่านผิดก็ตอบ 401 — ต้องแสดงข้อความ ไม่ใช่ล้าง session
   */
  public async login(email: string, password: string): Promise<{ access_token: string; user: any }> {
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
    const authToken = token || getToken();
    if (!authToken) return null;
    try {
      const res = await apiFetch('/auth/me', {
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
