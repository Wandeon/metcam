/**
 * Main App Component
 */

import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { Dashboard } from '@/pages/Dashboard';
import { MatchesEnhanced as Matches } from '@/pages/MatchesEnhanced';
import { Preview } from '@/pages/Preview';
import { Panorama } from '@/pages/Panorama';
import { Development } from '@/pages/Development';
import { Logs } from '@/pages/Logs';
import { Health } from '@/pages/Health';
import { Login } from '@/pages/Login';
import { Video, Home, Film, Eye, Code, FileText, Activity, LogOut, Menu, X, RefreshCw, Layers } from 'lucide-react';
import { apiService } from '@/services/api';
import { wsManager } from '@/services/websocket';
import { webRtcService } from '@/services/webrtc';
import { useWsConnectionState } from '@/hooks/useWebSocket';

function App() {
  const isAuthenticated = !!localStorage.getItem('access_token');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [restartMessage, setRestartMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  const wsConnected = useWsConnectionState();

  // WebSocket lifecycle
  useEffect(() => {
    if (isAuthenticated) {
      wsManager.connect();
    }
    return () => {
      webRtcService.shutdown();
      wsManager.disconnect();
    };
  }, [isAuthenticated]);

  const handleRestartProduction = async () => {
    if (!window.confirm('Restart production API service? This will briefly interrupt the service.')) {
      return;
    }

    setRestarting(true);
    setRestartMessage(null);

    try {
      const result = await apiService.restartProduction();
      if (result.success) {
        setRestartMessage({ type: 'success', text: 'Production API restarted successfully' });
      } else {
        setRestartMessage({ type: 'error', text: result.message || 'Restart failed' });
      }
    } catch (err: any) {
      setRestartMessage({ type: 'error', text: err.message || 'Failed to restart production API' });
    } finally {
      setRestarting(false);
      setTimeout(() => setRestartMessage(null), 5000);
    }
  };

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
                to="/panorama"
                icon={<Layers className="w-5 h-5" />}
                label="Panorama"
                onClick={() => setSidebarOpen(false)}
              />
              <NavLink
                to="/matches"
                icon={<Film />}
                label="Matches"
                onClick={() => setSidebarOpen(false)}
              />
              <NavLink
                to="/health"
                icon={<Activity />}
                label="Health"
                onClick={() => setSidebarOpen(false)}
              />
              <NavLink
                to="/logs"
                icon={<FileText />}
                label="Logs"
                onClick={() => setSidebarOpen(false)}
              />
              <NavLink
                to="/development"
                icon={<Code />}
                label="Development"
                onClick={() => setSidebarOpen(false)}
              />
            </nav>
          </div>

          <div className="absolute bottom-0 left-0 right-0 p-6 space-y-3">
            <div className="flex items-center text-sm">
              {wsConnected ? (
                <>
                  <div className="w-2 h-2 bg-green-400 rounded-full mr-2" />
                  <span className="text-green-400">Live</span>
                </>
              ) : (
                <>
                  <div className="w-2 h-2 bg-yellow-400 rounded-full mr-2 animate-pulse" />
                  <span className="text-yellow-400">Reconnecting...</span>
                </>
              )}
            </div>
            {restartMessage && (
              <div className={`text-xs p-2 rounded ${
                restartMessage.type === 'success'
                  ? 'bg-green-900 text-green-100'
                  : 'bg-red-900 text-red-100'
              }`}>
                {restartMessage.text}
              </div>
            )}
            <button
              onClick={handleRestartProduction}
              disabled={restarting}
              className="flex items-center text-yellow-400 hover:text-yellow-300 transition-colors w-full disabled:opacity-50 disabled:cursor-not-allowed"
              title="Restart production API service"
            >
              <RefreshCw className={`w-5 h-5 mr-2 ${restarting ? 'animate-spin' : ''}`} />
              {restarting ? 'Restarting...' : 'Restart API'}
            </button>
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
            <Route path="/panorama" element={<Panorama />} />
            <Route path="/matches" element={<Matches />} />
            <Route path="/health" element={<Health />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/development" element={<Development />} />
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
