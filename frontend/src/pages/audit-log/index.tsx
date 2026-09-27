import React from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { EmptyState } from '../../components/common/EmptyState';
import { Download, Search, FileText, Lock } from 'lucide-react';
import { AuditEvent } from '../../types';
import { useAuth } from '../../context/AuthContext';

export default function AuditLog() {
  const { isAuthenticated } = useAuth();
  const events: AuditEvent[] = []; // Empty data as requested

  return (
    <div className="space-y-6">
      <PageHeader 
        title="Audit Trail" 
        subtitle="Immutable log of all system activities, approvals, and overrides"
        actions={
          <button
            disabled={!isAuthenticated}
            title={!isAuthenticated ? 'Sign in required to export' : ''}
            className={`flex items-center space-x-2 px-4 py-2 rounded-md text-sm font-medium shadow-sm transition ${
              !isAuthenticated
                ? 'bg-gray-100 text-gray-400 border border-gray-200 cursor-not-allowed'
                : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
            }`}
          >
            {!isAuthenticated ? <Lock className="w-4 h-4" /> : <Download className="w-4 h-4" />}
            <span>Export</span>
          </button>
        }
      />

      <div className="bg-white p-4 border border-gray-200 rounded-lg shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex flex-wrap gap-2">
          <button className="px-3 py-1.5 bg-blue-50 text-blue-700 text-sm font-medium rounded-md border border-blue-200">
            All Events
          </button>
          <button className="px-3 py-1.5 bg-white text-gray-600 text-sm font-medium rounded-md border border-gray-300 hover:bg-gray-50">
            Requisition Decision
          </button>
          <button className="px-3 py-1.5 bg-white text-gray-600 text-sm font-medium rounded-md border border-gray-300 hover:bg-gray-50">
            QC Override
          </button>
          <button className="px-3 py-1.5 bg-white text-gray-600 text-sm font-medium rounded-md border border-gray-300 hover:bg-gray-50">
            Hot Reload
          </button>
        </div>
        
        <div className="relative w-full md:w-64">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-4 w-4 text-gray-400" />
          </div>
          <input
            type="text"
            placeholder="Search audit logs..."
            className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
        {events.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timestamp</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Event Type</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actor</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Role</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Target Resource</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Summary</th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {/* Table rows would go here */}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8">
            <EmptyState 
              icon={FileText}
              title="No audit events recorded" 
              description="System activities will be logged automatically." 
            />
          </div>
        )}
      </div>
    </div>
  );
}

export const AuditLogPage = AuditLog;
