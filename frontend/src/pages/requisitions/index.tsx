import React, { useState } from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { StatCard } from '../../components/common/StatCard';
import { EmptyState } from '../../components/common/EmptyState';
import { ClipboardList, Filter, Lock } from 'lucide-react';
import { RequisitionRecord } from '../../types';
import { useAuth } from '../../context/AuthContext';

type FilterType = 'ALL' | 'PENDING' | 'APPROVED' | 'REJECTED';

export function RequisitionsPage() {
  const [filter, setFilter] = useState<FilterType>('ALL');
  const [threshold, setThreshold] = useState<number>(30);
  const { isAuthenticated } = useAuth();
  const requisitions: RequisitionRecord[] = [];

  const handleThresholdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!isAuthenticated) return;
    setThreshold(Number(e.target.value));
  };

  const Actions = (
    <div className="flex items-center space-x-2">
      {!isAuthenticated && <Lock className="w-3.5 h-3.5 text-gray-400" />}
      <label htmlFor="threshold" className="text-sm text-gray-600 font-medium">Auto-trigger Threshold (days):</label>
      <input
        type="number"
        id="threshold"
        disabled={!isAuthenticated}
        title={!isAuthenticated ? 'Sign in required to calibrate threshold' : ''}
        className={`w-20 px-2 py-1 border rounded-md text-sm shadow-sm ${
          !isAuthenticated ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed' : 'border-gray-300 focus:ring-blue-500 focus:border-blue-500'
        }`}
        value={threshold}
        onChange={handleThresholdChange}
        min="1"
        max="365"
      />
    </div>
  );

  return (
    <div className="space-y-6">
      <PageHeader 
        title="Parts Requisitions" 
        subtitle="Review and approve RUL-triggered spare parts requests" 
        actions={Actions}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total"
          value={0}
          icon={ClipboardList}
          accent="blue"
        />
        <StatCard
          label="Pending"
          value={0}
          icon={ClipboardList}
          accent="amber"
        />
        <StatCard
          label="Approved"
          value={0}
          icon={ClipboardList}
          accent="emerald"
        />
        <StatCard
          label="Rejected"
          value={0}
          icon={ClipboardList}
          accent="red"
        />
      </div>

      <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div className="flex space-x-4">
            {(['ALL', 'PENDING', 'APPROVED', 'REJECTED'] as FilterType[]).map((f) => (
              <button
                key={f}
                className={`text-sm font-medium px-3 py-2 border-b-2 ${
                  filter === f
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
                onClick={() => setFilter(f)}
              >
                {f.charAt(0) + f.slice(1).toLowerCase()} (0)
              </button>
            ))}
          </div>
          <div className="flex items-center text-gray-500">
            <Filter className="w-4 h-4 mr-2" />
            <span className="text-sm">Filter</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Requisition ID</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Asset</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Part</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Predicted RUL</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Urgency</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Requested At</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {/* Empty state handles rendering */}
            </tbody>
          </table>
          
          <div className="p-12 border-t border-gray-200">
            <EmptyState
              icon={ClipboardList}
              title="No requisitions found"
              description="There are currently no parts requisitions matching your filter criteria."
            />
          </div>
        </div>
      </div>
    </div>
  );
}
