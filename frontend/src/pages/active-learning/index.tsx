import React from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { StatCard } from '../../components/common/StatCard';
import { EmptyState } from '../../components/common/EmptyState';
import { BrainCircuit, RefreshCw, Database, CheckCircle2, Lock } from 'lucide-react';
import { DeflexQueueItem } from '../../types';
import { useAuth } from '../../context/AuthContext';

export function ActiveLearningPage() {
  const { isAuthenticated } = useAuth();
  const queueItems: DeflexQueueItem[] = [];
  const isQueueEmpty = queueItems.length === 0;

  const Actions = (
    <button
      disabled={!isAuthenticated || isQueueEmpty}
      title={!isAuthenticated ? 'Sign in required to trigger retraining' : undefined}
      className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-md shadow-sm border ${
        !isAuthenticated || isQueueEmpty 
          ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed' 
          : 'bg-indigo-600 text-white border-transparent hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500'
      }`}
    >
      {!isAuthenticated ? <Lock className="w-4 h-4" /> : <RefreshCw className="w-4 h-4" />}
      <span>{!isAuthenticated ? 'Sign In to Retrain' : 'Trigger Retrain'}</span>
    </button>
  );

  return (
    <div className="space-y-6">
      <PageHeader 
        title="Model Registry & Active Learning" 
        subtitle="Manage PatchCore versions and process inspector overrides" 
        actions={Actions}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatCard
          label="Active Model"
          value="--"
          icon={BrainCircuit}
          accent="indigo"
        />
        <StatCard
          label="Retrain Queue"
          value={0}
          icon={RefreshCw}
          accent="amber"
        />
        <StatCard
          label="Coreset Memory Bank"
          value="--"
          unit="vectors"
          icon={Database}
          accent="purple"
        />
      </div>

      <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden flex flex-col min-h-[400px]">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h3 className="text-lg font-medium text-gray-900">Active Learning Queue</h3>
        </div>
        
        <div className="overflow-x-auto flex-1">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sample ID</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Part SKU</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">AI Verdict</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ground Truth</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Inspector Note</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Queued At</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {/* Empty body */}
            </tbody>
          </table>
          
          <div className="h-full flex items-center justify-center p-12 mt-10">
             <EmptyState
                icon={CheckCircle2}
                title="Queue is empty"
                description="No inspector overrides pending for retraining."
              />
          </div>
        </div>
      </div>
    </div>
  );
}
