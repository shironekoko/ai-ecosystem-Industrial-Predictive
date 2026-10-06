import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '../../components/common/PageHeader';
import { EmptyState } from '../../components/common/EmptyState';
import { UserRole } from '../../types';
import { useAuth } from '../../context/AuthContext';
import {
  UserPlus,
  Key,
  Shield,
  UserX,
  Lock,
  ShieldAlert,
  ArrowLeft,
  Trash2,
  CheckCircle2,
  X,
  Mail,
  Building2,
  User as UserIcon,
} from 'lucide-react';

export default function UserManagementPage() {
  const navigate = useNavigate();
  const { isAuthenticated, user, usersList, updateUserRole, deleteUser, addUser } = useAuth();
  const isAdmin = isAuthenticated && user?.role === 'admin';

  // Add User Modal State
  const [showAddModal, setShowAddModal] = useState(false);
  const [newName, setNewName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newDepartment, setNewDepartment] = useState('');
  const [newRole, setNewRole] = useState<UserRole>('engineer');
  const [addError, setAddError] = useState('');

  // 1. RBAC Guard: If not an Admin, deny access completely!
  if (!isAdmin) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl border border-red-100 shadow-sm p-8 text-center space-y-4">
          <div className="w-14 h-14 rounded-2xl bg-red-50 text-red-600 flex items-center justify-center mx-auto border border-red-100">
            <ShieldAlert className="w-7 h-7" />
          </div>
          <div>
            <span className="inline-block px-2.5 py-0.5 rounded-full bg-red-100 text-red-700 text-[11px] font-semibold tracking-wider uppercase mb-2">
              403 · Access Restricted
            </span>
            <h2 className="text-xl font-bold text-gray-900">Administrator Privileges Required</h2>
            <p className="text-xs text-gray-500 mt-2 leading-relaxed">
              This console is strictly restricted to System Administrators. Maintenance Engineers and guest accounts are not permitted to view user rosters, reassign roles, or manage accounts.
            </p>
          </div>
          <div className="pt-2">
            <button
              onClick={() => navigate('/dashboard')}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-gray-900 hover:bg-gray-800 text-white rounded-lg text-xs font-semibold shadow-sm transition"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Return to Dashboard</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  const handleCreateUser = (e: React.FormEvent) => {
    e.preventDefault();
    setAddError('');
    if (!newName || !newEmail) {
      setAddError('Please enter both name and email.');
      return;
    }
    addUser({
      name: newName,
      email: newEmail,
      role: newRole,
      department: newDepartment || (newRole === 'admin' ? 'Operations' : 'Maintenance Team'),
    });
    setNewName('');
    setNewEmail('');
    setNewDepartment('');
    setShowAddModal(false);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users & Roles"
        subtitle="Role-based access control, privilege assignments, and team management"
        actions={
          <button
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 transition"
          >
            <UserPlus className="h-4 w-4" />
            Add User
          </button>
        }
      />

      {/* Role Definitions Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 border-l-4 border-l-indigo-500 p-5">
          <div className="flex items-center gap-2.5 mb-2">
            <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
              <Key className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-gray-900">Maintenance Engineer</h3>
          </div>
          <p className="text-xs text-gray-500 leading-relaxed">
            Monitors machines and RUL predictions, removes tools at REPLACE_NOW, reviews AI blade VB measurements (accept or measure on the bench) and closes replacement work orders. Restricted from user administration.
          </p>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 border-l-4 border-l-purple-500 p-5">
          <div className="flex items-center gap-2.5 mb-2">
            <div className="p-2 bg-purple-50 rounded-lg text-purple-600">
              <Shield className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-gray-900">System Administrator</h3>
          </div>
          <p className="text-xs text-gray-500 leading-relaxed">
            Everything an engineer can do, plus starting vision retrains, promoting/rejecting candidates, switching model versions, and managing user accounts and roles.
          </p>
        </div>
      </div>

      {/* User Directory Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
          <div>
            <h3 className="text-sm font-bold text-gray-900">User Directory</h3>
            <p className="text-xs text-gray-500">Only administrators can modify roles or remove accounts</p>
          </div>
          <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-purple-50 text-purple-700 border border-purple-200">
            Admin Governance Active
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-xs">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-5 py-3 text-left font-semibold text-gray-500 uppercase tracking-wider">User</th>
                <th className="px-5 py-3 text-left font-semibold text-gray-500 uppercase tracking-wider">Department</th>
                <th className="px-5 py-3 text-left font-semibold text-gray-500 uppercase tracking-wider">Role & Permissions</th>
                <th className="px-5 py-3 text-left font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-5 py-3 text-right font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-100">
              {usersList.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12">
                    <EmptyState
                      icon={UserX}
                      title="No registered users found"
                      description="Add team members to provision access to the platform."
                    />
                  </td>
                </tr>
              ) : (
                usersList.map((u) => {
                  const isSelf = u.id === user.id;
                  return (
                    <tr key={u.id} className="hover:bg-gray-50/60 transition">
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-gray-100 text-gray-600 flex items-center justify-center font-bold">
                            {u.name ? u.name.slice(0, 2).toUpperCase() : 'U'}
                          </div>
                          <div>
                            <div className="font-semibold text-gray-900 flex items-center gap-1.5">
                              <span>{u.name}</span>
                              {isSelf && (
                                <span className="text-[10px] font-normal px-1.5 py-0.2 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                                  You
                                </span>
                              )}
                            </div>
                            <div className="text-gray-400">{u.email}</div>
                          </div>
                        </div>
                      </td>

                      <td className="px-5 py-3.5 whitespace-nowrap text-gray-600 font-medium">
                        {u.department}
                      </td>

                      <td className="px-5 py-3.5 whitespace-nowrap">
                        {/* Admin can change any user's role */}
                        <div className="flex items-center gap-2">
                          <select
                            value={u.role}
                            onChange={(e) => updateUserRole(u.id, e.target.value as UserRole)}
                            className={`px-2.5 py-1 rounded-md text-xs font-semibold border cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                              u.role === 'admin'
                                ? 'bg-purple-50 text-purple-700 border-purple-200'
                                : 'bg-indigo-50 text-indigo-700 border-indigo-200'
                            }`}
                          >
                            <option value="engineer">Maintenance Engineer</option>
                            <option value="admin">System Administrator</option>
                          </select>
                        </div>
                      </td>

                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                          Active
                        </span>
                      </td>

                      <td className="px-5 py-3.5 whitespace-nowrap text-right">
                        {/* Admin can delete users, but not their own active account */}
                        <button
                          onClick={() => {
                            if (window.confirm(`Are you sure you want to delete user ${u.name}?`)) {
                              deleteUser(u.id);
                            }
                          }}
                          disabled={isSelf}
                          title={isSelf ? 'Cannot delete your own active account' : 'Remove user account'}
                          className={`p-1.5 rounded-lg transition ${
                            isSelf
                              ? 'text-gray-300 cursor-not-allowed'
                              : 'text-gray-400 hover:text-red-600 hover:bg-red-50'
                          }`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add User Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-gray-50">
              <div className="flex items-center gap-2">
                <UserPlus className="w-4 h-4 text-indigo-600" />
                <h3 className="font-bold text-sm text-gray-900">Provision New User</h3>
              </div>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-md"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="p-6 space-y-4">
              {addError && (
                <div className="p-2.5 rounded-lg bg-red-50 text-red-600 text-xs border border-red-200">
                  {addError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1.5">
                  Initial Role Assignment
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setNewRole('engineer')}
                    className={`py-2 px-3 text-xs font-medium rounded-lg border text-center transition ${
                      newRole === 'engineer'
                        ? 'bg-indigo-50 border-indigo-300 text-indigo-700 shadow-sm'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    Engineer
                  </button>
                  <button
                    type="button"
                    onClick={() => setNewRole('admin')}
                    className={`py-2 px-3 text-xs font-medium rounded-lg border text-center transition ${
                      newRole === 'admin'
                        ? 'bg-purple-50 border-purple-300 text-purple-700 shadow-sm'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    Administrator
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Full Name</label>
                <div className="relative">
                  <UserIcon className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    required
                    placeholder="e.g. Alex Mercer"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    className="pl-9 pr-3 py-2 w-full border border-gray-300 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Email Address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                  <input
                    type="email"
                    required
                    placeholder="a.mercer@plant.corp"
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    className="pl-9 pr-3 py-2 w-full border border-gray-300 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Department</label>
                <div className="relative">
                  <Building2 className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    placeholder="e.g. Predictive Maintenance Lab"
                    value={newDepartment}
                    onChange={(e) => setNewDepartment(e.target.value)}
                    className="pl-9 pr-3 py-2 w-full border border-gray-300 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-2 rounded-lg border border-gray-300 text-xs font-medium text-gray-700 hover:bg-gray-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-sm transition"
                >
                  Provision User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export { UserManagementPage };
