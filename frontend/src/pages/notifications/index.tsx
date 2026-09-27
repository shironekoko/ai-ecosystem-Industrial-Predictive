import React from 'react';
import { PageHeader } from '../../components/common/PageHeader';
import { EmptyState } from '../../components/common/EmptyState';
import { AlertNotification } from '../../types';
import { CheckCheck, BellOff, Lock } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function NotificationsPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Notifications"
        subtitle="System alerts from background workers and prognostic engines"
        actions={
          <button
            disabled={!isAuthenticated}
            title={!isAuthenticated ? 'Sign in required to mark alerts as read' : ''}
            className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium shadow-sm ring-1 ring-inset ${
              !isAuthenticated 
                ? 'bg-gray-100 text-gray-400 ring-gray-200 cursor-not-allowed'
                : 'bg-white text-gray-700 ring-gray-300 hover:bg-gray-50'
            }`}
          >
            {!isAuthenticated ? <Lock className="h-4 w-4" /> : <CheckCheck className="h-4 w-4" />}
            <span>Mark All Read</span>
          </button>
        }
      />

      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8" aria-label="Tabs">
          {[
            { name: 'All', count: 0, current: true },
            { name: 'Critical', count: 0, current: false },
            { name: 'Warning', count: 0, current: false },
            { name: 'Info', count: 0, current: false },
          ].map((tab) => (
            <button
              key={tab.name}
              className={`
                whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium
                ${
                  tab.current
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                }
              `}
            >
              {tab.name}
              <span
                className={`ml-3 hidden rounded-full py-0.5 px-2.5 text-xs font-medium md:inline-block ${
                  tab.current ? 'bg-indigo-100 text-indigo-600' : 'bg-gray-100 text-gray-900'
                }`}
              >
                {tab.count}
              </span>
            </button>
          ))}
        </nav>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-8">
        <EmptyState
          icon={BellOff}
          title="No notifications"
          description="System alerts from BiLSTM and Vision workers will appear here when triggered."
        />
      </div>
    </div>
  );
}

export { NotificationsPage };
