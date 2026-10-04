/**
 * WebSocket client: /api/v1/tool-life/stream
 *
 * ข้อความจาก backend (ข้อมูลจริงจากชุดข้อมูล LUH เล่นตามเวลาจริง — ไม่มีการจำลองค่าในฝั่งเว็บ)
 *  - snapshot : สถานะทุกเครื่อง + ผลพยากรณ์ล่าสุด
 *  - run      : ฟีเจอร์ + ผลพยากรณ์ของรันที่เพิ่งจบ
 *  - event    : เหตุการณ์/การแจ้งเตือน
 *  - frame    : สัญญาณดิบทุก 0.1 วินาที (เฉพาะเครื่องที่เลือกดู)
 * ถ้าการเชื่อมต่อหลุด จะลองเชื่อมใหม่เรื่อย ๆ และแสดงสถานะ DISCONNECTED (ไม่เติมข้อมูลปลอม)
 */
import type { StreamConnectionStatus, StreamMessage } from '../types';

type Listener = (msg: StreamMessage) => void;
type StatusListener = (s: StreamConnectionStatus) => void;

class ToolLifeStream {
  private ws: WebSocket | null = null;
  private listeners = new Set<Listener>();
  private statusListeners = new Set<StatusListener>();
  private status: StreamConnectionStatus = 'DISCONNECTED';
  private waveform: number | null = null;
  private retry: ReturnType<typeof setTimeout> | null = null;
  private refCount = 0;

  private url(): string {
    const explicit = (import.meta as any).env?.VITE_WS_URL as string | undefined;
    if (explicit) return explicit;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}/api/v1/tool-life/stream`;
  }

  private setStatus(s: StreamConnectionStatus) {
    this.status = s;
    this.statusListeners.forEach((l) => l(s));
  }

  private connect() {
    if (this.ws || this.refCount === 0) return;
    this.setStatus('CONNECTING');
    const qs = this.waveform ? `?waveform=${this.waveform}` : '';
    const ws = new WebSocket(this.url() + qs);
    this.ws = ws;
    ws.onopen = () => {
      this.setStatus('CONNECTED');
      ws.send(JSON.stringify({ waveform: this.waveform })); // ค่าที่เลือกระหว่างกำลังเชื่อมต่อ
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as StreamMessage;
        this.listeners.forEach((l) => l(msg));
      } catch {
        /* ignore malformed */
      }
    };
    ws.onclose = () => {
      this.ws = null;
      this.setStatus('DISCONNECTED');
      if (this.refCount > 0) this.retry = setTimeout(() => this.connect(), 2000);
    };
    ws.onerror = () => ws.close();
  }

  subscribe(listener: Listener, onStatus?: StatusListener): () => void {
    this.listeners.add(listener);
    if (onStatus) {
      this.statusListeners.add(onStatus);
      onStatus(this.status);
    }
    this.refCount += 1;
    this.connect();
    return () => {
      this.listeners.delete(listener);
      if (onStatus) this.statusListeners.delete(onStatus);
      this.refCount -= 1;
      if (this.refCount <= 0) {
        this.refCount = 0;
        if (this.retry) clearTimeout(this.retry);
        this.ws?.close();
        this.ws = null;
      }
    };
  }

  /** เลือกเครื่องที่ต้องการรับสัญญาณดิบ (null = ไม่รับ) */
  setWaveform(machine: number | null) {
    this.waveform = machine;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ waveform: machine }));
    }
  }
}

export const toolLifeStream = new ToolLifeStream();
