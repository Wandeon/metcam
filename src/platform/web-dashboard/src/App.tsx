/**
 * Main App Component
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { Dashboard } from '@/pages/Dashboard';
import { Matches } from '@/pages/Matches';
import { Login } from '@/pages/Login';
import { Video, Home, Film, Settings, LogOut } from 'lucide-react';

function App() {
  const isAuthenticated = !!localStorage.getItem('access_token');

  if (!isAuthenticated) {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    );
  }

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-100">
        {/* Sidebar */}
        <aside className="fixed left-0 top-0 h-full w-64 bg-gray-900 text-white">
          <div className="p-6">
            <div className="flex items-center mb-8">
              <Video className="w-8 h-8 text-green-500 mr-2" />
              <h1 className="text-xl font-bold">FootballVision Pro</h1>
            </div>

            <nav className="space-y-2">
              <NavLink to="/" icon={<Home />} label="Dashboard" />
              <NavLink to="/matches" icon={<Film />} label="Matches" />
              <NavLink to="/settings" icon={<Settings />} label="Settings" />
            </nav>
          </div>

          <div className="absolute bottom-0 left-0 right-0 p-6">
            <button
              onClick={() => {
                localStorage.clear();
                window.location.href = '/login';
              }}
              className="flex items-center text-gray-400 hover:text-white transition-colors"
            >
              <LogOut className="w-5 h-5 mr-2" />
              Logout
            </button>
          </div>
        </aside>

        {/* Main Content */}
        <main className="ml-64">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/matches" element={<Matches />} />
            <Route path="/settings" element={<div className="p-6">Settings (Coming Soon)</div>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

const NavLink: React.FC<{ to: string; icon: React.ReactNode; label: string }> = ({
  to,
  icon,
  label,
}) => {
  return (
    <Link
      to={to}
      className="flex items-center px-4 py-3 rounded-lg hover:bg-gray-800 transition-colors"
    >
      <span className="w-5 h-5 mr-3">{icon}</span>
      {label}
    </Link>
  );
};

export default App;