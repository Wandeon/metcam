/**
 * Main App Component
 */

import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { Dashboard } from '@/pages/Dashboard';
import { Matches } from '@/pages/Matches';
import { Preview } from '@/pages/Preview';
import { Calibration } from '@/pages/Calibration';
import { ActivityLog } from '@/pages/ActivityLog';
import { Login } from '@/pages/Login';
import { Video, Home, Film, Eye, Focus, Settings, LogOut, Menu, X, Activity } from 'lucide-react';

function App() {
  const isAuthenticated = !!localStorage.getItem('access_token');
  const [sidebarOpen, setSidebarOpen] = useState(false);

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
        {/* Mobile Header */}
        <div className="lg:hidden fixed top-0 left-0 right-0 bg-gray-900 text-white p-4 flex items-center justify-between z-50">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 hover:bg-gray-800 rounded touch-manipulation"
          >
            {sidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
          <div className="flex items-center">
            <Video className="w-6 h-6 text-green-500 mr-2" />
            <h1 className="text-lg font-bold">FootballVision Pro</h1>
          </div>
          <div className="w-10" /> {/* Spacer */}
        </div>

        {/* Overlay for mobile */}
        {sidebarOpen && (
          <div
            className="lg:hidden fixed inset-0 bg-black bg-opacity-50 z-40"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <aside
          className={`
            fixed left-0 top-0 h-full w-64 bg-gray-900 text-white z-50 transition-transform duration-300
            ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
            lg:translate-x-0
          `}
        >
          <div className="p-6 mt-16 lg:mt-0">
            <div className="hidden lg:flex items-center mb-8">
              <Video className="w-8 h-8 text-green-500 mr-2" />
              <h1 className="text-xl font-bold">FootballVision Pro</h1>
            </div>

            <nav className="space-y-2">
              <NavLink
                to="/"
                icon={<Home />}
                label="Dashboard"
                onClick={() => setSidebarOpen(false)}
              />
              <NavLink
                to="/preview"
                icon={<Eye />}
                label="Preview"
                onClick={() => setSidebarOpen(false)}
              />
              <NavLink
                to="/calibration"
                icon={<Focus />}
                label="Calibration"
                onClick={() => setSidebarOpen(false)}
              />
              <NavLink
                to="/matches"
                icon={<Film />}
                label="Matches"
                onClick={() => setSidebarOpen(false)}
              />
              <NavLink
                to="/activity"
                icon={<Activity />}
                label="Activity Log"
                onClick={() => setSidebarOpen(false)}
              />
              <NavLink
                to="/settings"
                icon={<Settings />}
                label="Settings"
                onClick={() => setSidebarOpen(false)}
              />
            </nav>
          </div>

          <div className="absolute bottom-0 left-0 right-0 p-6">
            <button
              onClick={() => {
                localStorage.clear();
                window.location.href = '/login';
              }}
              className="flex items-center text-gray-400 hover:text-white transition-colors w-full"
            >
              <LogOut className="w-5 h-5 mr-2" />
              Logout
            </button>
          </div>
        </aside>

        {/* Main Content */}
        <main className="pt-16 lg:pt-0 lg:ml-64">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/preview" element={<Preview />} />
            <Route path="/calibration" element={<Calibration />} />
            <Route path="/matches" element={<Matches />} />
            <Route path="/activity" element={<ActivityLog />} />
            <Route path="/settings" element={<div className="p-6">Settings (Coming Soon)</div>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

const NavLink: React.FC<{
  to: string;
  icon: React.ReactNode;
  label: string;
  onClick?: () => void;
}> = ({ to, icon, label, onClick }) => {
  return (
    <Link
      to={to}
      onClick={onClick}
      className="flex items-center px-4 py-3 rounded-lg hover:bg-gray-800 transition-colors touch-manipulation"
    >
      <span className="w-5 h-5 mr-3">{icon}</span>
      {label}
    </Link>
  );
};

export default App;