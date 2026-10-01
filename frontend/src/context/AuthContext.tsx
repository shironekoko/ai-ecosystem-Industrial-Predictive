import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, UserRole } from '../types';
import { api } from '../services/api';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  usersList: User[];
  login: (email: string, password: string) => Promise<void>;
  register: (data: { name: string; email: string; password: string; role: UserRole; department?: string; title?: string }) => Promise<void>;
  logout: () => void;
  updateUserRole: (userId: string, newRole: UserRole) => Promise<void>;
  deleteUser: (userId: string) => Promise<void>;
  addUser: (userData: { name: string; email: string; password?: string; role: UserRole; department: string }) => Promise<void>;
  refreshUsers: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const AUTH_STORAGE_KEY = 'pdm_auth_user';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const stored = localStorage.getItem(AUTH_STORAGE_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  const [usersList, setUsersList] = useState<User[]>([]);

  const isAuthenticated = !!user;

  // Refresh users directory from PostgreSQL backend
  const refreshUsers = useCallback(async () => {
    try {
      const backendUsers = await api.getUsers();
      if (Array.isArray(backendUsers)) {
        const mapped: User[] = backendUsers.map((bu: any) => ({
          id: String(bu.id),
          name: bu.name || bu.email.split('@')[0],
          email: bu.email,
          role: (bu.role as UserRole) || 'engineer',
          title: bu.title || (bu.role === 'admin' ? 'System Administrator' : 'Maintenance Engineer'),
          department: bu.department || 'Maintenance Team',
        }));
        setUsersList(mapped);
      }
    } catch (err) {
      console.warn('[AuthContext] Failed to load users from backend:', err);
    }
  }, []);

  // Fetch users on mount and verify session
  useEffect(() => {
    refreshUsers();

    // Verify token validity with backend
    const token = localStorage.getItem('pdm_access_token');
    if (token) {
      api.getMe(token).then((me) => {
        if (me && me.email) {
          const verifiedUser: User = {
            id: String(me.id),
            name: me.name || me.full_name || me.email.split('@')[0],
            email: me.email,
            role: (me.role as UserRole) || 'engineer',
            title: me.title || (me.role === 'admin' ? 'System Administrator' : 'Maintenance Engineer'),
            department: me.department || 'Maintenance Team',
          };
          setUser(verifiedUser);
          localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(verifiedUser));
        } else {
          setUser(null);
          localStorage.removeItem(AUTH_STORAGE_KEY);
          localStorage.removeItem('pdm_access_token');
          localStorage.removeItem('pdm_refresh_token');
        }
      }).catch(() => {
        // If token expired/invalid, clear session
        console.warn('[AuthContext] Token validation failed');
        setUser(null);
        localStorage.removeItem(AUTH_STORAGE_KEY);
        localStorage.removeItem('pdm_access_token');
        localStorage.removeItem('pdm_refresh_token');
      });
    }
  }, [refreshUsers]);

  const login = async (email: string, password: string) => {
    // Authenticate with real PostgreSQL backend API
    const authData = await api.login(email, password);
    const authenticatedUser: User = {
      id: String(authData.user.id),
      name: authData.user.name || authData.user.full_name || email.split('@')[0],
      email: authData.user.email,
      role: (authData.user.role as UserRole) || 'engineer',
      title: authData.user.title || (authData.user.role === 'admin' ? 'System Administrator' : 'Maintenance Engineer'),
      department: authData.user.department || (authData.user.role === 'admin' ? 'Operations & Security' : 'Predictive Maintenance Lab'),
    };

    setUser(authenticatedUser);
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authenticatedUser));
    if (authData.access_token) {
      localStorage.setItem('pdm_access_token', authData.access_token);
    }
    if (authData.refresh_token) {
      localStorage.setItem('pdm_refresh_token', authData.refresh_token);
    }

    await refreshUsers();
  };

  const register = async (data: { name: string; email: string; password: string; role: UserRole; department?: string; title?: string }) => {
    // Register account in PostgreSQL
    await api.register({
      name: data.name,
      email: data.email,
      password: data.password,
      role: data.role,
      department: data.department || (data.role === 'admin' ? 'Operations & Security' : 'Maintenance Department'),
      title: data.title || (data.role === 'admin' ? 'System Administrator' : 'Maintenance Engineer'),
    });

    // Automatically login with new credentials
    await login(data.email, data.password);
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(AUTH_STORAGE_KEY);
    localStorage.removeItem('pdm_access_token');
    localStorage.removeItem('pdm_refresh_token');
  };

  // Admin action: Change role of any user via backend API
  const updateUserRole = async (userId: string, newRole: UserRole) => {
    if (user?.role !== 'admin') {
      alert('Access Denied: Only administrators can modify user roles.');
      return;
    }

    await api.updateUserRole(userId, newRole);

    if (user?.id === userId) {
      const updatedUser: User = {
        ...user,
        role: newRole,
        title: newRole === 'admin' ? 'System Administrator' : 'Maintenance Engineer',
      };
      setUser(updatedUser);
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(updatedUser));
    }

    await refreshUsers();
  };

  // Admin action: Delete user via backend API
  const deleteUser = async (userId: string) => {
    if (user?.role !== 'admin') {
      alert('Access Denied: Only administrators can delete users.');
      return;
    }

    if (user?.id === userId) {
      alert('Cannot delete your own active administrator account.');
      return;
    }

    await api.deleteUser(userId);
    await refreshUsers();
  };

  // Admin action: Add user via backend API
  const addUser = async (userData: { name: string; email: string; password?: string; role: UserRole; department: string }) => {
    if (user?.role !== 'admin') {
      alert('Access Denied: Only administrators can create users.');
      return;
    }

    await api.createUser({
      name: userData.name,
      email: userData.email,
      role: userData.role,
      department: userData.department,
      title: userData.role === 'admin' ? 'System Administrator' : 'Maintenance Engineer',
      password: userData.password || 'default123',
    });

    await refreshUsers();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        usersList,
        login,
        register,
        logout,
        updateUserRole,
        deleteUser,
        addUser,
        refreshUsers,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
