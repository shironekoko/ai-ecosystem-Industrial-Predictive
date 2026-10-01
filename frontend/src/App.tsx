import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
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
import { api } from './services/api';
import { ProtectedRoute } from './components/ProtectedRoute';

const AppRoutes = () => {
  const { user } = useAuth();
  const currentRole = user?.role || 'engineer';
  const [unreadAlertCount, setUnreadAlertCount] = useState<number>(0);

  React.useEffect(() => {
    api.getAlarms().then((alarms) => {
      if (Array.isArray(alarms)) {
        const unread = alarms.filter((a: any) => !a.isRead).length;
        setUnreadAlertCount(unread);
      }
    });
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<ProtectedRoute />}>
          <Route
            element={
              <AppLayout
                currentRole={currentRole}
                onRoleChange={() => {}} 
                unreadAlertCount={unreadAlertCount}
                retrainQueueCount={0}
              />
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="machine-monitoring" element={<MachineMonitoringPage />} />
            <Route path="visual-qc" element={<VisualQcPage />} />
            <Route path="active-learning" element={<ActiveLearningPage />} />
            <Route path="audit-log" element={<AuditLogPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="user-management" element={<UserManagementPage />} />
            <Route path="reports" element={<ReportsPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
};

export default App;
