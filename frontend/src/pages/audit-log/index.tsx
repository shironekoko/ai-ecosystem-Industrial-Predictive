import React, { useState, useEffect } from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { EmptyState } from '../../components/common/EmptyState';
import { History, Search, Filter } from 'lucide-react';
import { AuditEvent } from '../../types';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';

/** เหตุการณ์ที่ backend บันทึก (ตัวกรองใช้การค้นหาบางส่วน: VISION_MODEL = promote/reject/สลับเวอร์ชัน) */
const EVENT_TYPES: [string, string][] = [
  ['TOOL_REPLACED', 'Tool removed (RUL)'],
  ['TOOL_LIFE_OVERRIDE', 'REPLACE_NOW overridden'],
  ['VISION_INSPECTION', 'Blade images captured'],
  ['VISION_REVIEW', 'Inspection reviewed'],
  ['TOOL_ISSUED', 'Tool issued from crib'],
  ['TOOL_INSTALLED', 'New tool installed'],
  ['VISION_RETRAIN_REQUESTED', 'Retrain started (auto)'],
  ['VISION_MODEL', 'Model promote / reject / switch'],
];

export function AuditLogPage() {
  const { isAuthenticated } = useAuth();
  const [filterType, setFilterType] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [events, setEvents] = useState<AuditEvent[]>([]);

  useEffect(() => {
    let isMounted = true;
    const fetchLogs = () => {
      api.getAuditLogs(filterType, searchQuery).then((data) => {
        if (isMounted && data && Array.isArray(data.items)) {
          setEvents(data.items);
        }
      });
    };

    fetchLogs();
    const interval = setInterval(fetchLogs, 4000);
    window.addEventListener('focus', fetchLogs);

    return () => {
      isMounted = false;
      clearInterval(interval);
      window.removeEventListener('focus', fetchLogs);
    };
  }, [filterType, searchQuery]);

  const filteredEvents = events;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Trail & Sign-Off History"
        subtitle="Chronological immutable record of human-in-the-loop decisions, model promotions, and system events"
      />

      {/* Audit Matrix Card */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        {/* Controls Ribbon */}
        <div className="px-5 py-4 border-b border-gray-100 flex flex-wrap items-center justify-between gap-4 bg-gray-50/50">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search actor, tool, or summary..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-3 py-1.5 border border-gray-200 rounded-lg text-xs w-64 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>

            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <Filter className="w-3.5 h-3.5 text-gray-400" />
              <span>Type:</span>
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="px-2.5 py-1.5 border border-gray-200 rounded-lg text-xs bg-white text-gray-700 font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="ALL">All Event Types</option>
                {EVENT_TYPES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <span className="text-xs font-mono text-gray-400">Total Entries: {events.length}</span>
        </div>

        {/* Audit Table or Empty State */}
        {filteredEvents.length === 0 ? (
          <div className="py-14">
            <EmptyState
              icon={History}
              title="No Audit Trail Records"
              description="Human-in-the-loop tool inspections, engineer sign-offs, and system governance events will be securely recorded here in real-time."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50 text-[11px] uppercase tracking-wider text-gray-400 font-semibold border-b border-gray-100">
                <tr>
                  <th className="px-5 py-3">Event ID</th>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Event Type</th>
                  <th className="px-4 py-3">Actor</th>
                  <th className="px-4 py-3">Target Resource</th>
                  <th className="px-5 py-3">Summary</th>
                  <th className="px-4 py-3 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 font-mono">
                {filteredEvents.map((ev) => (
                  <tr key={ev.id} className="hover:bg-gray-50/70 transition">
                    <td className="px-5 py-3.5 font-bold text-gray-900">{ev.id}</td>
                    <td className="px-4 py-3.5 text-gray-500">{ev.timestamp}</td>
                    <td className="px-4 py-3.5">
                      <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-700 font-bold text-[10px]">
                        {ev.eventType}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 font-sans font-medium text-gray-900">{ev.actor}</td>
                    <td className="px-4 py-3.5 text-indigo-600 font-bold">{ev.targetResource}</td>
                    <td className="px-5 py-3.5 font-sans text-gray-600 max-w-xs truncate">{ev.summary}</td>
                    <td className="px-4 py-3.5 text-right font-sans">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        ev.status === 'SUCCESS' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                        ev.status === 'WARNING' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                        ev.status === 'FAILED' || ev.status === 'ERROR' ? 'bg-red-50 text-red-700 border-red-200' :
                        'bg-gray-50 text-gray-700 border-gray-200'
                      }`}>
                        {ev.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default AuditLogPage;
