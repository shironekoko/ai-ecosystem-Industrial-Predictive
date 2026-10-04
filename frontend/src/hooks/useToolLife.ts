import { useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { toolLifeStream } from '../services/telemetryStream';
import type {
  FleetSnapshot,
  RunRecord,
  StreamConnectionStatus,
  StreamEvent,
  WaveFrame,
} from '../types';

/** สถานะทั้งกองเครื่อง (snapshot จาก WebSocket; โหลดครั้งแรกผ่าน REST) */
export function useFleet() {
  const [fleet, setFleet] = useState<FleetSnapshot | null>(null);
  const [conn, setConn] = useState<StreamConnectionStatus>('CONNECTING');
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .getFleet()
      .then((f) => alive && setFleet(f))
      .catch((e) => alive && setError(String(e.message || e)));
    const unsub = toolLifeStream.subscribe(
      (msg) => {
        if (msg.type === 'snapshot') {
          setFleet(msg);
          setError(null);
        } else if (msg.type === 'event') {
          setEvents((prev) => [msg, ...prev].slice(0, 60));
        }
      },
      (s) => setConn(s),
    );
    return () => {
      alive = false;
      unsub();
    };
  }, []);

  return { fleet, conn, events, error };
}

/** ประวัติรายรันของเครื่องหนึ่ง (REST ครั้งแรก แล้วต่อท้ายจากข้อความ run) */
export function useMachineHistory(machine: number) {
  const [history, setHistory] = useState<RunRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setHistory([]);
    api
      .getMachine(machine, true)
      .then((m) => alive && setHistory(m.history || []))
      .catch(() => {})
      .finally(() => alive && setLoading(false));
    const unsub = toolLifeStream.subscribe((msg) => {
      if (msg.type === 'run' && msg.machine === machine) {
        setHistory((prev) => (prev.length && prev[prev.length - 1].run === msg.record.run ? prev : [...prev, msg.record]));
      } else if (msg.type === 'snapshot') {
        const m = msg.machines.find((x) => x.machine === machine);
        if (m && m.run_index === 0 && m.state === 'IDLE') setHistory([]); // ถูกรีเซ็ต
      }
    });
    return () => {
      alive = false;
      unsub();
    };
  }, [machine]);

  return { history, loading };
}

export interface WavePoint {
  t: number;
  fx: number;
  fy: number;
  fz: number;
  sp: number;
  ax: number;
  ay: number;
}

/** สัญญาณดิบล่าสุดของเครื่องที่เลือก (หน้าต่างเลื่อน ~windowS วินาทีของข้อมูล) */
export function useWaveform(machine: number, windowS = 3) {
  const [points, setPoints] = useState<WavePoint[]>([]);
  const [run, setRun] = useState<number | null>(null);
  const buf = useRef<WavePoint[]>([]);
  const lastRun = useRef<number | null>(null);

  useEffect(() => {
    buf.current = [];
    setPoints([]);
    toolLifeStream.setWaveform(machine);
    const unsub = toolLifeStream.subscribe((msg) => {
      if (msg.type !== 'frame' || msg.machine !== machine) return;
      const f = msg as WaveFrame;
      if (lastRun.current !== f.run) {
        buf.current = [];
        lastRun.current = f.run;
        setRun(f.run);
      }
      for (let i = 0; i < f.fx.length; i++) {
        buf.current.push({ t: +(f.t + i * f.dt).toFixed(3), fx: f.fx[i], fy: f.fy[i], fz: f.fz[i], sp: f.sp[i], ax: f.ax[i], ay: f.ay[i] });
      }
      const tEnd = buf.current[buf.current.length - 1]?.t ?? 0;
      buf.current = buf.current.filter((p) => p.t >= tEnd - windowS);
      setPoints([...buf.current]);
    });
    return () => {
      unsub();
      toolLifeStream.setWaveform(null);
    };
  }, [machine, windowS]);

  return { points, run };
}
