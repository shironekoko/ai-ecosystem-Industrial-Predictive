import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, UserRole } from '../types';
import { api } from '../services/api';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  usersList: User[];
  login: (email: string, role: UserRole, name?: string) => void;
  register: (data: { name: string; email: string; role: UserRole; department?: string; title?: string }) => void;
  logout: () => void;
  updateUserRole: (userId: string, newRole: UserRole) => void;
  deleteUser: (userId: string) => void;
  addUser: (userData: { name: string; email: string; role: UserRole; department: string }) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const AUTH_STORAGE_KEY = 'pdm_auth_user';
const USERS_STORAGE_KEY = 'pdm_users_directory';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const stored = localStorage.getItem(AUTH_STORAGE_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  const [usersList, setUsersList] = useState<User[]>(() => {
    try {
      const stored = localStorage.getItem(USERS_STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const isAuthenticated = !!user;

  // Fetch registered users from backend and merge
  useEffect(() => {
    api.getUsers().then((backendUsers) => {
      if (Array.isArray(backendUsers) && backendUsers.length > 0) {
        setUsersList((prev) => {
          const existingEmails = new Set(prev.map((u) => u.email.toLowerCase()));
          const newOnes: User[] = backendUsers
            .filter((bu: any) => !existingEmails.has(bu.email.toLowerCase()))
            .map((bu: any) => ({
              id: bu.id,
              name: bu.name,
              email: bu.email,
              role: bu.role as UserRole,
              title: bu.title || (bu.role === 'admin' ? 'System Administrator' : 'Maintenance Engineer'),
              department: bu.department || 'Maintenance Team',
            }));
          return [...prev, ...newOnes];
        });
      }
    });
  }, []);

  // Sync usersList to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(USERS_STORAGE_KEY, JSON.stringify(usersList));
    } catch (e) {
      console.error('Failed to save users directory', e);
    }
  }, [usersList]);

  const login = (email: string, role: UserRole, name?: string) => {
    // Check if user already exists in directory
    const existing = usersList.find((u) => u.email.toLowerCase() === email.toLowerCase());
    const finalRole = existing ? existing.role : role;
    const finalName = existing ? existing.name : (name || email.split('@')[0] || 'User');

    const authenticatedUser: User = {
      id: existing ? existing.id : 'USR-' + Math.random().toString(36).substring(2, 7).toUpperCase(),
      name: finalName,
      email,
      role: finalRole,
      title: finalRole === 'admin' ? 'System Administrator' : 'Maintenance Engineer',
      department: existing ? existing.department : (finalRole === 'admin' ? 'Operations & Security' : 'Predictive Maintenance Lab'),
    };

    setUser(authenticatedUser);
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authenticatedUser));

    // Ensure user is in directory
    if (!existing) {
      setUsersList((prev) => [...prev, authenticatedUser]);
    }
  };

  const register = (data: { name: string; email: string; role: UserRole; department?: string; title?: string }) => {
    const newUser: User = {
      id: 'USR-' + Math.random().toString(36).substring(2, 7).toUpperCase(),
      name: data.name,
      email: data.email,
      role: data.role,
      title: data.title || (data.role === 'admin' ? 'System Administrator' : 'Maintenance Engineer'),
      department: data.department || (data.role === 'admin' ? 'Operations & Security' : 'Maintenance Department'),
    };

    setUser(newUser);
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(newUser));

    setUsersList((prev) => {
      const filtered = prev.filter((u) => u.email.toLowerCase() !== data.email.toLowerCase());
      return [...filtered, newUser];
    });
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(AUTH_STORAGE_KEY);
  };

  // Admin action: Change role of any user
  const updateUserRole = (userId: string, newRole: UserRole) => {
    if (user?.role !== 'admin') {
      alert('Access Denied: Only administrators can modify user roles.');
      return;
    }

    api.updateUserRole(userId, newRole);

    setUsersList((prev) =>
      prev.map((u) => {
        if (u.id === userId) {
          const updated: User = {
            ...u,
            role: newRole,
            title: newRole === 'admin' ? 'System Administrator' : 'Maintenance Engineer',
          };
          // If editing self, update active session too
          if (user?.id === userId) {
            setUser(updated);
            localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(updated));
          }
          return updated;
        }
        return u;
      })
    );
  };

  // Admin action: Delete user
  const deleteUser = (userId: string) => {
    if (user?.role !== 'admin') {
      alert('Access Denied: Only administrators can delete users.');
      return;
    }

    if (user?.id === userId) {
      alert('Cannot delete your own active administrator account.');
      return;
    }

    api.deleteUser(userId);
    setUsersList((prev) => prev.filter((u) => u.id !== userId));
  };

  // Admin action: Add user
  const addUser = (userData: { name: string; email: string; role: UserRole; department: string }) => {
    if (user?.role !== 'admin') {
      alert('Access Denied: Only administrators can create users.');
      return;
    }

    api.createUser(userData);

    const newUser: User = {
      id: 'USR-' + Math.random().toString(36).substring(2, 7).toUpperCase(),
      name: userData.name,
      email: userData.email,
      role: userData.role,
      title: userData.role === 'admin' ? 'System Administrator' : 'Maintenance Engineer',
      department: userData.department,
    };

    setUsersList((prev) => [...prev, newUser]);
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
