/**
 * Real-time CNC Spindle Telemetry Streaming Service
 * Production WebSocket client for: /api/v1/telemetry/spindle/stream
 *
 * Prepared for real-time streaming API.
 * Keeps stream idle/empty when server is not connected.
 */

import { TelemetryPacket, StreamConnectionStatus } from '../types';

type PacketListener = (packet: TelemetryPacket) => void;
type StatusListener = (status: StreamConnectionStatus) => void;

export class TelemetryStreamService {
  private static instance: TelemetryStreamService;

  // WebSocket configuration
  private wsUrl: string;
  private ws: WebSocket | null = null;
  private connectionStatus: StreamConnectionStatus = 'CONNECTING';
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private isPaused: boolean = false;

  // Event Listeners
  private packetListeners: Set<PacketListener> = new Set();
  private statusListeners: Set<StatusListener> = new Set();

  private constructor() {
    const defaultWsHost = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';
    const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.wsUrl =
      (import.meta as any).env?.VITE_WS_URL ||
      `${protocol}//${defaultWsHost}/api/v1/telemetry/spindle/stream`;

    this.connectWebSocket();
  }

  public static getInstance(): TelemetryStreamService {
    if (!TelemetryStreamService.instance) {
      TelemetryStreamService.instance = new TelemetryStreamService();
    }
    return TelemetryStreamService.instance;
  }

  /**
   * Subscribe to incoming live telemetry packets from the WebSocket server
   */
  public subscribe(listener: PacketListener): () => void {
    this.packetListeners.add(listener);
    return () => {
      this.packetListeners.delete(listener);
    };
  }

  /**
   * Subscribe to connection status changes
   */
  public subscribeStatus(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    listener(this.connectionStatus);
    return () => {
      this.statusListeners.delete(listener);
    };
  }

  public getConnectionStatus(): StreamConnectionStatus {
    return this.connectionStatus;
  }

  public getWsUrl(): string {
    return this.wsUrl;
  }

  public pause(): void {
    this.isPaused = true;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify({ command: 'PAUSE_STREAM' }));
      } catch {
        // ignore send error
      }
    }
  }

  public resume(): void {
    this.isPaused = false;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify({ command: 'RESUME_STREAM' }));
      } catch {
        // ignore send error
      }
    }
  }

  public isStreamPaused(): boolean {
    return this.isPaused;
  }

  public reconnect(): void {
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        // ignore
      }
      this.ws = null;
    }
    this.connectWebSocket();
  }

  /**
   * Connect to backend WebSocket endpoint
   */
  private connectWebSocket(): void {
    if (typeof WebSocket === 'undefined') {
      this.updateStatus('DISCONNECTED');
      return;
    }

    this.updateStatus('CONNECTING');

    try {
      this.ws = new WebSocket(this.wsUrl);

      this.ws.onopen = () => {
        this.updateStatus('CONNECTED');
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        if (this.isPaused) return;
        try {
          const packet: TelemetryPacket = JSON.parse(event.data);
          this.emitPacket(packet);
        } catch (err) {
          console.error('[TelemetryStream] Failed to parse incoming WebSocket packet:', err);
        }
      };

      this.ws.onerror = () => {
        this.updateStatus('DISCONNECTED');
      };

      this.ws.onclose = () => {
        this.updateStatus('DISCONNECTED');
        // Retry connection in background every 10 seconds
        if (!this.reconnectTimer) {
          this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.connectWebSocket();
          }, 10000);
        }
      };
    } catch {
      this.updateStatus('DISCONNECTED');
    }
  }

  private updateStatus(status: StreamConnectionStatus): void {
    this.connectionStatus = status;
    this.statusListeners.forEach((listener) => listener(status));
  }

  private emitPacket(packet: TelemetryPacket): void {
    this.packetListeners.forEach((listener) => listener(packet));
  }
}

export const telemetryStream = TelemetryStreamService.getInstance();
