import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  AlertTriangle,
  Info,
  CheckCircle2,
  ScanEye,
  CheckCheck,
  Filter,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';
import { PageHeader } from '../../components/common/PageHeader';
import { StatusBadge } from '../../components/common/StatusBadge';
import { EmptyState } from '../../components/common/EmptyState';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';

export interface AlarmItem {
  id: string;
  severity: 'CRITICAL' | 'WARNING' | 'INFO';
  title: string;
  message: string;
  sourceService: string;
  machineId: string;
  toolRef?: string;
  timestamp: string;
  isRead: boolean;
  actionUrl?: string;
}

export function NotificationsPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const [activeTab, setActiveTab] = useState<'ALL' | 'CRITICAL' | 'WARNING' | 'INFO'>('ALL');
  const [alarms, setAlarms] = useState<AlarmItem[]>([]);

  useEffect(() => {
    api.getAlarms(activeTab).then((data) => {
      if (Array.isArray(data)) {
        setAlarms(data);
      }
    });
  }, [activeTab]);

  const criticalCount = alarms.filter((a) => a.severity === 'CRITICAL').length;
  const warningCount = alarms.filter((a) => a.severity === 'WARNING').length;
  const unreadCount = alarms.filter((a) => !a.isRead).length;

  const filteredAlarms = alarms;

  const handleMarkAllRead = async () => {
    await api.markAllAlarmsRead();
    setAlarms((prev) => prev.map((a) => ({ ...a, isRead: true })));
  };

  const handleDismiss = async (id: string) => {
    await api.deleteAlarm(id);
    setAlarms((prev) => prev.filter((a) => a.id !== id));
  };

  const handleItemClick = async (alarm: AlarmItem) => {
    if (!alarm.isRead) {
      await api.markAlarmRead(alarm.id);
      setAlarms((prev) => prev.map((a) => (a.id === alarm.id ? { ...a, isRead: true } : a)));
    }
    if (alarm.actionUrl) {
      navigate(alarm.actionUrl);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Alarms & Notifications"
        subtitle="Real-time cutting force threshold trips, optical wear detections, and safety interlocks"
        actions={
          <div className="flex items-center gap-2">
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-xs font-semibold text-gray-700 shadow-sm transition"
              >
                <CheckCheck className="w-3.5 h-3.5 text-gray-500" />
                <span>Mark All Read</span>
              </button>
            )}
            <StatusBadge
              status={criticalCount > 0 ? 'critical' : warningCount > 0 ? 'warning' : 'connected'}
              label={criticalCount > 0 ? 'SAFETY ALARMS ACTIVE' : 'SYSTEM NOMINAL'}
            />
          </div>
        }
      />

      {/* KPI Severity Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 bg-white border border-gray-200 rounded-xl shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs text-gray-500 font-semibold block">Total Alerts</span>
            <span className="text-2xl font-mono font-bold text-gray-900">{alarms.length}</span>
          </div>
          <div className="p-2.5 bg-gray-50 text-gray-600 rounded-xl">
            <Bell className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 bg-white border border-gray-200 rounded-xl shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs text-rose-600 font-semibold block">Critical Halts</span>
            <span className="text-2xl font-mono font-bold text-rose-600">{criticalCount}</span>
          </div>
          <div className="p-2.5 bg-rose-50 text-rose-600 rounded-xl">
            <ShieldAlert className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 bg-white border border-gray-200 rounded-xl shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs text-amber-600 font-semibold block">Wear Warnings</span>
            <span className="text-2xl font-mono font-bold text-amber-600">{warningCount}</span>
          </div>
          <div className="p-2.5 bg-amber-50 text-amber-600 rounded-xl">
            <AlertTriangle className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 bg-white border border-gray-200 rounded-xl shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs text-emerald-600 font-semibold block">System Status</span>
            <span className="text-base font-bold text-emerald-700 mt-1 block">
              {alarms.length === 0 ? 'Normal / 0 Faults' : `${unreadCount} Unread`}
            </span>
          </div>
          <div className="p-2.5 bg-emerald-50 text-emerald-600 rounded-xl">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Alarm Filter Ribbon & List */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100 flex flex-wrap items-center justify-between gap-3 bg-gray-50/50">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <span className="text-xs font-bold text-gray-700 uppercase tracking-wider">Severity Filter:</span>
            <div className="flex items-center gap-1">
              {(['ALL', 'CRITICAL', 'WARNING', 'INFO'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-2.5 py-1 rounded text-xs font-semibold transition ${
                    activeTab === tab
                      ? 'bg-gray-900 text-white shadow-sm'
                      : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Alarms Feed */}
        {filteredAlarms.length === 0 ? (
          <div className="py-14">
            <EmptyState
              icon={CheckCircle2}
              title="No Active System Alarms"
              description="Spindle cutting forces, dynamic vibration, and optical edge verification are within normal operational limits. Real-time alerts will appear here when cutting anomalies occur."
            />
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filteredAlarms.map((alarm) => (
              <div
                key={alarm.id}
                className={`p-4 transition flex flex-col sm:flex-row items-start justify-between gap-4 ${
                  !alarm.isRead ? 'bg-indigo-50/20' : 'bg-white hover:bg-gray-50/60'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`p-2 rounded-lg mt-0.5 shrink-0 ${
                      alarm.severity === 'CRITICAL'
                        ? 'bg-rose-100 text-rose-700'
                        : alarm.severity === 'WARNING'
                        ? 'bg-amber-100 text-amber-800'
                        : 'bg-blue-100 text-blue-700'
                    }`}
                  >
                    {alarm.severity === 'CRITICAL' ? (
                      <ShieldAlert className="w-4 h-4" />
                    ) : alarm.severity === 'WARNING' ? (
                      <AlertTriangle className="w-4 h-4" />
                    ) : (
                      <Info className="w-4 h-4" />
                    )}
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-xs text-gray-900">{alarm.title}</span>
                      <span className="text-[10px] font-mono text-gray-400">({alarm.id})</span>
                      {alarm.toolRef && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 font-semibold">
                          {alarm.toolRef}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-600 mt-1 leading-relaxed max-w-2xl">{alarm.message}</p>
                    <div className="flex items-center gap-3 text-[11px] text-gray-400 mt-2 font-mono">
                      <span>Source: {alarm.sourceService}</span>
                      <span>·</span>
                      <span>Target: {alarm.machineId}</span>
                      <span>·</span>
                      <span>Time: {alarm.timestamp}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                  {alarm.actionUrl && (
                    <button
                      onClick={() => handleItemClick(alarm)}
                      className="flex items-center gap-1 px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold rounded-lg transition cursor-pointer"
                    >
                      <ScanEye className="w-3.5 h-3.5" />
                      <span>Inspect</span>
                    </button>
                  )}
                  <button
                    onClick={() => handleDismiss(alarm.id)}
                    className="px-2.5 py-1.5 text-xs text-gray-400 hover:text-gray-700 rounded transition"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default NotificationsPage;
