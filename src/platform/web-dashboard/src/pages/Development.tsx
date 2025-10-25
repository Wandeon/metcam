import React, { useState, useEffect } from 'react';
import { apiService } from '@/services/api';
import {
  GitBranch, GitPullRequest, RefreshCw,
  Server, Upload, FileText, Activity,
  CheckCircle, AlertCircle, ChevronDown, ChevronUp, Code, X
} from 'lucide-react';

interface DevStatus {
  services: {
    production: {
      active: boolean;
      branch: string;
      commit: string;
    };
    development: {
      active: boolean;
      branch: string;
      commit: string;
      has_changes: boolean;
    };
  };
  api_port: string;
}

interface GitStatus {
  branch: string;
  commit: string;
  commit_message: string;
  has_changes: boolean;
  changes: string[];
  ahead: number;
  behind: number;
}

interface SystemInfo {
  cpu: {
    percent: number;
    count: number;
  };
  memory: {
    total_gb: number;
    used_gb: number;
    available_gb: number;
    percent: number;
  };
  disk: {
    root: {
      total_gb: number;
      used_gb: number;
      free_gb: number;
      percent: number;
    };
    recordings: {
      total_gb: number;
      used_gb: number;
      free_gb: number;
      percent: number;
    };
  };
}

export const Development: React.FC = () => {
  const [devStatus, setDevStatus] = useState<DevStatus | null>(null);
  const [gitStatus, setGitStatus] = useState<GitStatus | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [logs, setLogs] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Operation states
  const [pulling, setPulling] = useState(false);
  const [building, setBuilding] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [deploying, setDeploying] = useState(false);

  // UI state
  const [showLogs, setShowLogs] = useState(false);
  const [logService, setLogService] = useState<'dev' | 'prod'>('dev');

  const fetchDevStatus = async () => {
    try {
      const data = await apiService.getDevStatus();
      setDevStatus(data);
    } catch (err) {
      console.error('Failed to fetch dev status:', err);
    }
  };

  const fetchGitStatus = async () => {
    try {
      const data = await apiService.getGitStatus();
      setGitStatus(data);
    } catch (err) {
      console.error('Failed to fetch git status:', err);
    }
  };

  const fetchSystemInfo = async () => {
    try {
      const data = await apiService.getSystemInfo();
      setSystemInfo(data);
    } catch (err) {
      console.error('Failed to fetch system info:', err);
    }
  };

  const fetchLogs = async () => {
    try {
      const data = await apiService.getDevLogs(logService, 100);
      setLogs(data.logs);
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([
        fetchDevStatus(),
        fetchGitStatus(),
        fetchSystemInfo()
      ]);
      setLoading(false);
    };

    loadData();
    // No auto-refresh - user can manually refresh when needed
  }, []);

  useEffect(() => {
    if (showLogs) {
      fetchLogs();
      // Logs only refresh when you click the refresh button or switch services
    }
  }, [showLogs, logService]);

  const handleGitPull = async () => {
    setPulling(true);
    setError(null);
    try {
      const result = await apiService.gitPull();
      if (result.success) {
        setSuccess('Successfully pulled latest changes from develop');
        await fetchGitStatus();
      } else {
        setError(result.error || 'Failed to pull changes');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to pull changes');
    } finally {
      setPulling(false);
      setTimeout(() => setSuccess(null), 5000);
    }
  };

  const handleBuildUI = async () => {
    setBuilding(true);
    setError(null);
    try {
      const result = await apiService.buildDevUI();
      if (result.success) {
        setSuccess('Successfully built and deployed development UI');
      } else {
        setError(result.error || 'Failed to build UI');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to build UI');
    } finally {
      setBuilding(false);
      setTimeout(() => setSuccess(null), 5000);
    }
  };

  const handleSwitchService = async (target: 'dev' | 'prod') => {
    setSwitching(true);
    setError(null);
    try {
      await apiService.switchService(target);
      setSuccess(`Switching to ${target} (will take ~5 seconds)`);
      setTimeout(() => {
        window.location.reload();
      }, 6000);
    } catch (err: any) {
      setError(err.message || 'Failed to switch service');
      setSwitching(false);
    }
  };

  const handleDeploy = async () => {
    if (!window.confirm('Deploy to production? This will update the live system.')) {
      return;
    }

    setDeploying(true);
    setError(null);
    try {
      await apiService.deployToProduction(true);
      setSuccess('Deployment started (will take ~2-3 minutes)');
    } catch (err: any) {
      setError(err.message || 'Failed to deploy');
    } finally {
      setDeploying(false);
      setTimeout(() => setSuccess(null), 5000);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <RefreshCw className="w-12 h-12 animate-spin mx-auto mb-4" />
          <p>Loading development environment...</p>
        </div>
      </div>
    );
  }

  const currentService = devStatus?.services.production.active ? 'production' : 'development';

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center">
            <Code className="w-8 h-8 mr-3" />
            Development Environment
          </h1>
          <p className="text-gray-600 mt-1">
            Manage development workflow and deploy to production
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={async () => {
              await Promise.all([
                fetchDevStatus(),
                fetchGitStatus(),
                fetchSystemInfo()
              ]);
            }}
            className="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg flex items-center"
            title="Refresh status"
          >
            <RefreshCw className="w-5 h-5" />
          </button>
          <div className={`px-4 py-2 rounded-lg font-semibold ${
            currentService === 'production'
              ? 'bg-green-100 text-green-800'
              : 'bg-blue-100 text-blue-800'
          }`}>
            {currentService.toUpperCase()}
          </div>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
          <AlertCircle className="w-5 h-5 text-red-600 mr-3 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-red-800 font-medium">Error</p>
            <p className="text-red-700 text-sm mt-1">{error}</p>
          </div>
          <button onClick={() => setError(null)} className="ml-4">
            <X className="w-5 h-5 text-red-400 hover:text-red-600" />
          </button>
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-start">
          <CheckCircle className="w-5 h-5 text-green-600 mr-3 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-green-800 font-medium">Success</p>
            <p className="text-green-700 text-sm mt-1">{success}</p>
          </div>
          <button onClick={() => setSuccess(null)} className="ml-4">
            <X className="w-5 h-5 text-green-400 hover:text-green-600" />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Git Status */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold flex items-center">
              <GitBranch className="w-6 h-6 mr-2" />
              Git Status
            </h2>
            <button
              onClick={handleGitPull}
              disabled={pulling}
              className="flex items-center px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {pulling ? (
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <GitPullRequest className="w-4 h-4 mr-2" />
              )}
              {pulling ? 'Pulling...' : 'Pull Latest'}
            </button>
          </div>

          {gitStatus && (
            <div className="space-y-3">
              <div className="flex items-center justify-between py-2 border-b">
                <span className="text-gray-600">Branch:</span>
                <span className="font-mono font-semibold">{gitStatus.branch}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b">
                <span className="text-gray-600">Commit:</span>
                <span className="font-mono text-sm">{gitStatus.commit}</span>
              </div>
              <div className="py-2 border-b">
                <span className="text-gray-600 block mb-1">Message:</span>
                <span className="text-sm">{gitStatus.commit_message}</span>
              </div>
              {gitStatus.behind > 0 && (
                <div className="bg-yellow-50 p-3 rounded">
                  <p className="text-yellow-800 text-sm">
                    Behind by {gitStatus.behind} commit{gitStatus.behind > 1 ? 's' : ''}
                  </p>
                </div>
              )}
              {gitStatus.has_changes && (
                <div className="bg-orange-50 p-3 rounded">
                  <p className="text-orange-800 text-sm font-medium mb-2">Uncommitted changes:</p>
                  <div className="font-mono text-xs space-y-1">
                    {gitStatus.changes.map((change, idx) => (
                      <div key={idx}>{change}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Service Control */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <Server className="w-6 h-6 mr-2" />
            Service Control
          </h2>

          {devStatus && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className={`p-4 rounded-lg border-2 ${
                  devStatus.services.production.active
                    ? 'border-green-500 bg-green-50'
                    : 'border-gray-200'
                }`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold">Production</span>
                    {devStatus.services.production.active && (
                      <CheckCircle className="w-5 h-5 text-green-600" />
                    )}
                  </div>
                  <div className="text-xs space-y-1">
                    <div className="font-mono">{devStatus.services.production.branch}</div>
                    <div className="text-gray-500">{devStatus.services.production.commit}</div>
                  </div>
                </div>

                <div className={`p-4 rounded-lg border-2 ${
                  devStatus.services.development.active
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200'
                }`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold">Development</span>
                    {devStatus.services.development.active && (
                      <CheckCircle className="w-5 h-5 text-blue-600" />
                    )}
                  </div>
                  <div className="text-xs space-y-1">
                    <div className="font-mono">{devStatus.services.development.branch}</div>
                    <div className="text-gray-500">{devStatus.services.development.commit}</div>
                  </div>
                </div>
              </div>

              <div className="flex space-x-3">
                <button
                  onClick={() => handleSwitchService('dev')}
                  disabled={switching || devStatus.services.development.active}
                  className="flex-1 py-3 px-4 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-semibold"
                >
                  {switching ? 'Switching...' : 'Switch to Dev'}
                </button>
                <button
                  onClick={() => handleSwitchService('prod')}
                  disabled={switching || devStatus.services.production.active}
                  className="flex-1 py-3 px-4 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed font-semibold"
                >
                  {switching ? 'Switching...' : 'Switch to Prod'}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Build & Deploy */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <Upload className="w-6 h-6 mr-2" />
            Build & Deploy
          </h2>

          <div className="space-y-3">
            <button
              onClick={handleBuildUI}
              disabled={building}
              className="w-full py-3 px-4 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed font-semibold flex items-center justify-center"
            >
              {building ? (
                <>
                  <RefreshCw className="w-5 h-5 mr-2 animate-spin" />
                  Building UI... (~2 min)
                </>
              ) : (
                <>
                  <RefreshCw className="w-5 h-5 mr-2" />
                  Build Dev UI
                </>
              )}
            </button>

            <button
              onClick={handleDeploy}
              disabled={deploying}
              className="w-full py-3 px-4 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed font-semibold flex items-center justify-center"
            >
              {deploying ? (
                <>
                  <RefreshCw className="w-5 h-5 mr-2 animate-spin" />
                  Deploying... (~3 min)
                </>
              ) : (
                <>
                  <Upload className="w-5 h-5 mr-2" />
                  Deploy to Production
                </>
              )}
            </button>

            <div className="bg-gray-50 p-3 rounded text-sm text-gray-600">
              <p className="font-medium mb-1">Deploy Process:</p>
              <ol className="list-decimal list-inside space-y-1">
                <li>Creates automatic backup</li>
                <li>Pulls latest from main branch</li>
                <li>Builds web dashboard</li>
                <li>Restarts production service</li>
              </ol>
            </div>
          </div>
        </div>

        {/* System Info */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <Activity className="w-6 h-6 mr-2" />
            System Status
          </h2>

          {systemInfo && (
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>CPU ({systemInfo.cpu.count} cores)</span>
                  <span className="font-semibold">{systemInfo.cpu.percent.toFixed(1)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all"
                    style={{ width: `${systemInfo.cpu.percent}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Memory</span>
                  <span className="font-semibold">
                    {systemInfo.memory.used_gb.toFixed(1)}GB / {systemInfo.memory.total_gb.toFixed(1)}GB
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-green-600 h-2 rounded-full transition-all"
                    style={{ width: `${systemInfo.memory.percent}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Root Disk</span>
                  <span className="font-semibold">
                    {systemInfo.disk.root.used_gb.toFixed(1)}GB / {systemInfo.disk.root.total_gb.toFixed(1)}GB
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all ${
                      systemInfo.disk.root.percent > 90 ? 'bg-red-600' : 'bg-purple-600'
                    }`}
                    style={{ width: `${systemInfo.disk.root.percent}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Recordings Disk</span>
                  <span className="font-semibold">
                    {systemInfo.disk.recordings.used_gb.toFixed(1)}GB / {systemInfo.disk.recordings.total_gb.toFixed(1)}GB
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all ${
                      systemInfo.disk.recordings.percent > 90 ? 'bg-red-600' : 'bg-orange-600'
                    }`}
                    style={{ width: `${systemInfo.disk.recordings.percent}%` }}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Logs */}
      <div className="bg-white rounded-lg shadow">
        <button
          onClick={() => setShowLogs(!showLogs)}
          className="w-full p-6 flex items-center justify-between hover:bg-gray-50"
        >
          <div className="flex items-center">
            <FileText className="w-6 h-6 mr-2" />
            <h2 className="text-xl font-semibold">Service Logs</h2>
          </div>
          {showLogs ? <ChevronUp /> : <ChevronDown />}
        </button>

        {showLogs && (
          <div className="p-6 border-t">
            <div className="flex items-center space-x-3 mb-4">
              <button
                onClick={() => setLogService('dev')}
                className={`px-4 py-2 rounded font-semibold ${
                  logService === 'dev'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                Development
              </button>
              <button
                onClick={() => setLogService('prod')}
                className={`px-4 py-2 rounded font-semibold ${
                  logService === 'prod'
                    ? 'bg-green-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                Production
              </button>
              <button
                onClick={fetchLogs}
                className="ml-auto px-4 py-2 bg-gray-200 rounded hover:bg-gray-300"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>

            <div className="bg-black text-green-400 p-4 rounded font-mono text-xs overflow-auto max-h-96">
              <pre className="whitespace-pre-wrap">{logs || 'No logs available'}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
