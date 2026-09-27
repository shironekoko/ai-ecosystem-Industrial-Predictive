import React from 'react';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '../../components/common/PageHeader';
import { StatCard } from '../../components/common/StatCard';
import { EmptyState } from '../../components/common/EmptyState';
import { StatusBadge } from '../../components/common/StatusBadge';
import { HardDrive, AlertTriangle, ClipboardCheck, BarChart3, Activity, Search, Bell, ListTodo } from 'lucide-react';
import { MachineAsset } from '../../types';
import { useAuth } from '../../context/AuthContext';

export function Dashboard() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const fleetAssets: MachineAsset[] = [];

  return (
    <div className="space-y-6">
      <PageHeader 
        title="Dashboard" 
        subtitle="Plant-wide operations command center" 
        actions={<StatusBadge status="disconnected" label="API Status" />} 
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          label="Monitored Assets"
          value={0}
          icon={HardDrive}
          accent="blue"
        />
        <StatCard
          label="Critical Alerts"
          value={0}
          icon={AlertTriangle}
          accent="red"
          trend="neutral"
          trendLabel="No data"
        />
        <StatCard
          label="Pending Requisitions"
          value={0}
          icon={ClipboardCheck}
          accent="amber"
        />
        <StatCard
          label="QC Defect Rate"
          value="--"
          icon={BarChart3}
          accent="purple"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <button 
          onClick={() => navigate('/visual-qc')}
          className="flex items-center p-4 bg-white border border-gray-200 rounded-lg shadow-sm hover:border-blue-500 hover:shadow-md transition-all text-left"
        >
          <div className="bg-blue-50 p-3 rounded-lg mr-4">
            <Search className="w-6 h-6 text-blue-600" />
          </div>
          <div>
            <h3 className="font-medium text-gray-900">Start QC Inspection</h3>
            <p className="text-sm text-gray-500">Run PatchCore inference</p>
          </div>
        </button>

        <button 
          onClick={() => navigate('/requisitions')}
          className="flex items-center p-4 bg-white border border-gray-200 rounded-lg shadow-sm hover:border-amber-500 hover:shadow-md transition-all text-left"
        >
          <div className="bg-amber-50 p-3 rounded-lg mr-4">
            <ListTodo className="w-6 h-6 text-amber-600" />
          </div>
          <div>
            <h3 className="font-medium text-gray-900">Review Requisitions</h3>
            <p className="text-sm text-gray-500">Approve pending parts</p>
          </div>
        </button>

        <button 
          onClick={() => navigate('/notifications')}
          className="flex items-center p-4 bg-white border border-gray-200 rounded-lg shadow-sm hover:border-red-500 hover:shadow-md transition-all text-left"
        >
          <div className="bg-red-50 p-3 rounded-lg mr-4">
            <Bell className="w-6 h-6 text-red-600" />
          </div>
          <div>
            <h3 className="font-medium text-gray-900">View Alerts</h3>
            <p className="text-sm text-gray-500">Check critical warnings</p>
          </div>
        </button>
      </div>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-8 bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden flex flex-col">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Asset Status</h3>
          </div>
          <div className="flex-1 p-6">
            <EmptyState
              icon={Activity}
              title="No machine assets registered"
              description="Connect sensors or register assets to begin predictive maintenance."
              action={
                isAuthenticated
                  ? {
                      label: 'Add First Asset',
                      onClick: () => navigate('/machine-monitoring')
                    }
                  : {
                      label: 'Sign In to Add Assets',
                      onClick: () => navigate('/login')
                    }
              }
            />
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4 bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden flex flex-col">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Recent Activity</h3>
          </div>
          <div className="flex-1 p-6 flex items-center justify-center text-gray-500">
            No activity recorded yet
          </div>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-6">
        <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-4">System Integration Status</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="flex items-center justify-between p-3 border border-gray-100 bg-gray-50 rounded-md">
            <span className="text-sm font-medium text-gray-700">API Gateway</span>
            <StatusBadge status="disconnected" size="sm" />
          </div>
          <div className="flex items-center justify-between p-3 border border-gray-100 bg-gray-50 rounded-md">
            <span className="text-sm font-medium text-gray-700">Redis Queue</span>
            <StatusBadge status="disconnected" size="sm" />
          </div>
          <div className="flex items-center justify-between p-3 border border-gray-100 bg-gray-50 rounded-md">
            <span className="text-sm font-medium text-gray-700">MinIO Storage</span>
            <StatusBadge status="disconnected" size="sm" />
          </div>
          <div className="flex items-center justify-between p-3 border border-gray-100 bg-gray-50 rounded-md">
            <span className="text-sm font-medium text-gray-700">MLflow Registry</span>
            <StatusBadge status="disconnected" size="sm" />
          </div>
        </div>
      </div>
    </div>
  );
}

export const DashboardPage = Dashboard;
export default Dashboard;
