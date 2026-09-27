import React from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { StatCard } from '../../components/common/StatCard';
import { EmptyState } from '../../components/common/EmptyState';
import { Clock, TrendingUp, Cpu, RefreshCw, BarChart3, PieChart, Download, Lock } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function ReportsPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Reports & Analytics"
        subtitle="Plant reliability metrics, defect distributions, and model performance"
        actions={
          <div className="flex items-center gap-4">
            <div className="inline-flex rounded-md shadow-sm" role="group">
              {['7D', '30D', '90D', 'YTD'].map((period, idx) => (
                <button
                  key={period}
                  type="button"
                  className={`
                    px-4 py-2 text-sm font-medium text-gray-900 bg-white border border-gray-200 
                    ${idx === 0 ? 'rounded-l-lg' : ''} 
                    ${idx === 3 ? 'rounded-r-lg' : ''} 
                    ${idx !== 0 ? '-ml-px' : ''}
                    hover:bg-gray-100 hover:text-indigo-700 focus:z-10 focus:ring-2 focus:ring-indigo-500 focus:text-indigo-700
                    ${period === '30D' ? 'bg-gray-50 text-indigo-700' : ''}
                  `}
                >
                  {period}
                </button>
              ))}
            </div>
            <button
              disabled={!isAuthenticated}
              title={!isAuthenticated ? 'Sign in required to export CSV' : ''}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium shadow-sm ring-1 ring-inset ${
                !isAuthenticated
                  ? 'bg-gray-100 text-gray-400 ring-gray-200 cursor-not-allowed'
                  : 'bg-white text-gray-700 ring-gray-300 hover:bg-gray-50'
              }`}
            >
              {!isAuthenticated ? <Lock className="h-4 w-4" /> : <Download className="h-4 w-4" />}
              CSV
            </button>
            <button
              disabled={!isAuthenticated}
              title={!isAuthenticated ? 'Sign in required to export PDF' : ''}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium shadow-sm ring-1 ring-inset ${
                !isAuthenticated
                  ? 'bg-gray-100 text-gray-400 ring-gray-200 cursor-not-allowed'
                  : 'bg-white text-gray-700 ring-gray-300 hover:bg-gray-50'
              }`}
            >
              {!isAuthenticated ? <Lock className="h-4 w-4" /> : <Download className="h-4 w-4" />}
              PDF
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          label="Plant MTBF"
          value="--"
          unit="hrs"
          icon={Clock}
          accent="blue"
        />
        <StatCard
          label="MTTR"
          value="--"
          unit="hrs"
          icon={TrendingUp}
          accent="emerald"
        />
        <StatCard
          label="Model F1-Score"
          value="--"
          icon={Cpu}
          accent="purple"
        />
        <StatCard
          label="False Positive Rate"
          value="--"
          icon={RefreshCw}
          accent="amber"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 flex flex-col min-h-[400px]">
          <div>
            <h3 className="text-base font-semibold leading-6 text-gray-900">Equipment MTBF Comparison</h3>
            <p className="text-sm text-gray-500">Mean Time Between Failures across key plant equipment</p>
          </div>
          <div className="mt-6 flex-1 border-2 border-dashed border-gray-200 rounded-lg flex items-center justify-center">
            <EmptyState
              icon={BarChart3}
              title="No data available"
              description="Sufficient operational data is required to render the MTBF comparison."
            />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 flex flex-col min-h-[400px]">
          <div>
            <h3 className="text-base font-semibold leading-6 text-gray-900">Defect Distribution (Screw)</h3>
            <p className="text-sm text-gray-500">Breakdown of identified defects on screw components</p>
          </div>
          <div className="mt-6 flex-1 border-2 border-dashed border-gray-200 rounded-lg flex items-center justify-center">
            <EmptyState
              icon={PieChart}
              title="No data available"
              description="Vision worker results are required to display defect distribution."
            />
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 flex flex-col min-h-[400px]">
        <div>
          <h3 className="text-base font-semibold leading-6 text-gray-900">Model Retraining History</h3>
          <p className="text-sm text-gray-500">Historical performance metrics and dataset drift indicators</p>
        </div>
        <div className="mt-6 flex-1 border-2 border-dashed border-gray-200 rounded-lg flex items-center justify-center">
          <EmptyState
            icon={Cpu}
            title="No history available"
            description="Continuous learning cycles have not yet been executed on the current models."
          />
        </div>
      </div>
    </div>
  );
}

export { ReportsPage };
