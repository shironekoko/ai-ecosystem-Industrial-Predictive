import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { UserRole } from '../../types';
import { Cpu, Shield, User, Lock, Mail, Building2, UserPlus, LogIn, ArrowRight } from 'lucide-react';

export function LoginPage() {
  const navigate = useNavigate();
  const { login, register, isAuthenticated, user, logout } = useAuth();

  const [mode, setMode] = useState<'login' | 'register'>('login');

  // Login form state
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginRole, setLoginRole] = useState<UserRole>('engineer');

  // Register form state
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regDepartment, setRegDepartment] = useState('');
  const [regRole, setRegRole] = useState<UserRole>('engineer');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPassword, setRegConfirmPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const handleLoginSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    if (!loginEmail || !loginPassword) {
      setErrorMsg('Please enter both email and password.');
      return;
    }
    login(loginEmail, loginRole);
    navigate('/dashboard');
  };

  const handleRegisterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    if (!regName || !regEmail || !regPassword) {
      setErrorMsg('Please fill in all required fields.');
      return;
    }
    if (regPassword !== regConfirmPassword) {
      setErrorMsg('Passwords do not match. Please try again.');
      return;
    }
    register({
      name: regName,
      email: regEmail,
      role: regRole,
      department: regDepartment || (regRole === 'admin' ? 'Operations' : 'Maintenance Team'),
    });
    navigate('/dashboard');
  };

  return (
    <div className="min-h-[82vh] flex items-center justify-center py-8 px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-md bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        {/* Brand Header */}
        <div className="p-6 text-center border-b border-gray-100 bg-gradient-to-b from-gray-50/70 to-white">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-600 to-indigo-500 mx-auto flex items-center justify-center shadow-sm mb-3">
            <Cpu className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-gray-900">
            Nonastreda CNC AI Platform
          </h1>
          <p className="mt-1 text-xs text-gray-500">
            Milling Tool Wear PdM & Dual-AI Quality Control
          </p>

          {/* Mode Switcher Tabs */}
          <div className="mt-5 grid grid-cols-2 p-1 bg-gray-100 rounded-lg text-xs font-medium">
            <button
              type="button"
              onClick={() => {
                setMode('login');
                setErrorMsg('');
              }}
              className={`py-2 rounded-md flex items-center justify-center gap-1.5 transition ${
                mode === 'login'
                  ? 'bg-white text-indigo-600 font-semibold shadow-sm'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              <LogIn className="w-3.5 h-3.5" />
              <span>Sign In</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('register');
                setErrorMsg('');
              }}
              className={`py-2 rounded-md flex items-center justify-center gap-1.5 transition ${
                mode === 'register'
                  ? 'bg-white text-indigo-600 font-semibold shadow-sm'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              <UserPlus className="w-3.5 h-3.5" />
              <span>Create Account</span>
            </button>
          </div>
        </div>

        {/* Form Body */}
        <div className="p-6">
          {errorMsg && (
            <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-xs text-red-600 font-medium">
              {errorMsg}
            </div>
          )}

          {isAuthenticated && (
            <div className="mb-5 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center justify-between">
              <div>
                <p className="font-semibold">Currently signed in as {user?.name}</p>
                <p className="text-[11px] text-emerald-600">{user?.email} · {user?.title}</p>
              </div>
              <button
                onClick={logout}
                className="px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100 rounded transition"
              >
                Sign Out
              </button>
            </div>
          )}

          {mode === 'login' ? (
            /* Login Form */
            <form onSubmit={handleLoginSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1.5">
                  Select Role
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setLoginRole('engineer')}
                    className={`py-2 px-3 text-xs font-medium rounded-lg border text-center flex items-center justify-center gap-1.5 transition ${
                      loginRole === 'engineer'
                        ? 'bg-indigo-50 border-indigo-300 text-indigo-700 shadow-sm'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <User className="w-3.5 h-3.5" />
                    Engineer
                  </button>
                  <button
                    type="button"
                    onClick={() => setLoginRole('admin')}
                    className={`py-2 px-3 text-xs font-medium rounded-lg border text-center flex items-center justify-center gap-1.5 transition ${
                      loginRole === 'admin'
                        ? 'bg-indigo-50 border-indigo-300 text-indigo-700 shadow-sm'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <Shield className="w-3.5 h-3.5" />
                    Admin
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                  <input
                    type="email"
                    required
                    placeholder="engineer@plant.corp"
                    className="pl-9 pr-3 py-2 w-full border border-gray-300 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                  <input
                    type="password"
                    required
                    placeholder="••••••••"
                    className="pl-9 pr-3 py-2 w-full border border-gray-300 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full mt-2 py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm flex items-center justify-center gap-2 transition shadow-sm"
              >
                <span>Sign In to System</span>
                <ArrowRight className="w-4 h-4" />
              </button>


              <div className="text-center pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setMode('register');
                    setErrorMsg('');
                  }}
                  className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                >
                  Don't have an account? Sign up here
                </button>
              </div>
            </form>
          ) : (
            /* Register Form */
            <form onSubmit={handleRegisterSubmit} className="space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1.5">
                  Target Role
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setRegRole('engineer')}
                    className={`py-2 px-3 text-xs font-medium rounded-lg border text-center flex items-center justify-center gap-1.5 transition ${
                      regRole === 'engineer'
                        ? 'bg-indigo-50 border-indigo-300 text-indigo-700 shadow-sm'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <User className="w-3.5 h-3.5" />
                    Maintenance Engineer
                  </button>
                  <button
                    type="button"
                    onClick={() => setRegRole('admin')}
                    className={`py-2 px-3 text-xs font-medium rounded-lg border text-center flex items-center justify-center gap-1.5 transition ${
                      regRole === 'admin'
                        ? 'bg-indigo-50 border-indigo-300 text-indigo-700 shadow-sm'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <Shield className="w-3.5 h-3.5" />
                    System Admin
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Full Name
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    required
                    placeholder="e.g. John Doe"
                    className="pl-9 pr-3 py-2 w-full border border-gray-300 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    value={regName}
                    onChange={(e) => setRegName(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Work Email
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                  <input
                    type="email"
                    required
                    placeholder="john@plant.corp"
                    className="pl-9 pr-3 py-2 w-full border border-gray-300 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Department / Plant Line
                </label>
                <div className="relative">
                  <Building2 className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    placeholder="e.g. Turbine Line 1"
                    className="pl-9 pr-3 py-2 w-full border border-gray-300 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    value={regDepartment}
                    onChange={(e) => setRegDepartment(e.target.value)}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Password
                  </label>
                  <input
                    type="password"
                    required
                    placeholder="••••••••"
                    className="px-3 py-2 w-full border border-gray-300 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Confirm
                  </label>
                  <input
                    type="password"
                    required
                    placeholder="••••••••"
                    className="px-3 py-2 w-full border border-gray-300 rounded-lg text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    value={regConfirmPassword}
                    onChange={(e) => setRegConfirmPassword(e.target.value)}
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full mt-3 py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm flex items-center justify-center gap-2 transition shadow-sm"
              >
                <span>Create Account & Enter</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <div className="text-center pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setMode('login');
                    setErrorMsg('');
                  }}
                  className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                >
                  Already have an account? Sign in here
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

export const LoginPageComponent = LoginPage;
export default LoginPage;
