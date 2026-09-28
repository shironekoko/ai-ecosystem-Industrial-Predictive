import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { AppLayout } from './components/layout/AppLayout';
import { LoginPage } from './pages/login';
import { DashboardPage } from './pages/dashboard';
import { MachineMonitoringPage } from './pages/machine-monitoring';
import { VisualQcPage } from './pages/visual-qc';
import { ActiveLearningPage } from './pages/active-learning';
import { AuditLogPage } from './pages/audit-log';
import { NotificationsPage } from './pages/notifications';
import { UserManagementPage } from './pages/user-management';
import { ReportsPage } from './pages/reports';
import { UserRole } from './types';

export const App: React.FC = () => {
  const [currentRole, setCurrentRole] = useState<UserRole>('engineer');

  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route
            path="/"
            element={
              <AppLayout
                currentRole={currentRole}
                onRoleChange={setCurrentRole}
                retrainQueueCount={0}
                unreadAlertCount={0}
              />
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="login" element={<LoginPage />} />
            <Route path="machine-monitoring" element={<MachineMonitoringPage />} />
            <Route path="visual-qc" element={<VisualQcPage />} />
            <Route path="active-learning" element={<ActiveLearningPage />} />
            <Route path="audit-log" element={<AuditLogPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="user-management" element={<UserManagementPage />} />
            <Route path="reports" element={<ReportsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
