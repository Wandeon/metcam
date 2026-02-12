import { useState, useEffect, useCallback } from 'react';
import { useWsCommand } from '@/hooks/useWebSocket';
import { FileText, AlertCircle, Activity, RefreshCw } from 'lucide-react';

type LogType = 'health' | 'alerts' | 'watchdog';

interface LogData {
  log_type: string;
  lines: string[];
  total_lines: number;
  message?: string;
}

interface StructuredAlert {
  ts: string;
  event_type: string;
  severity: string;
  message: string;
  details?: Record<string, unknown>;
}

function parseStructuredAlert(line: string): StructuredAlert | null {
  try {
    const parsed = JSON.parse(line);
    if (
      parsed
      && typeof parsed === 'object'
      && typeof parsed.ts === 'string'
      && typeof parsed.event_type === 'string'
      && typeof parsed.severity === 'string'
      && typeof parsed.message === 'string'
    ) {
      return parsed as StructuredAlert;
    }
  } catch {
    // Not structured JSON.
  }
  return null;
}

function formatAlertTimestamp(value?: string): string {
  if (!value) {
    return 'Unknown time';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function Logs() {
  const [selectedLog, setSelectedLog] = useState<LogType>('health');
  const [logData, setLogData] = useState<LogData | null>(null);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const { sendCommand, connected: wsConnected } = useWsCommand();

  const fetchLogs = useCallback(async (logType: LogType) => {
    setLoading(true);
    try {
      let data: LogData;

      if (wsConnected) {
        try {
          data = await sendCommand('get_logs', { log_type: logType, lines: 200 });
        } catch {
          const response = await fetch(`/api/v1/logs/${logType}?lines=200`);
          data = await response.json();
        }
      } else {
        const response = await fetch(`/api/v1/logs/${logType}?lines=200`);
        data = await response.json();
      }

      if (data.lines) {
        data.lines = data.lines.reverse();
      }
      setLogData(data);
    } catch (error) {
      console.error('Failed to fetch logs:', error);
      setLogData(null);
    } finally {
      setLoading(false);
    }
  }, [wsConnected, sendCommand]);

  useEffect(() => {
    fetchLogs(selectedLog);
  }, [selectedLog, fetchLogs]);

  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchLogs(selectedLog);
    }, 5000);

    return () => clearInterval(interval);
  }, [selectedLog, autoRefresh, fetchLogs]);

  const logTabs = [
    { id: 'health' as LogType, label: 'System Health', icon: Activity },
    { id: 'alerts' as LogType, label: 'Alerts', icon: AlertCircle },
    { id: 'watchdog' as LogType, label: 'Watchdog', icon: FileText },
  ];
  const structuredAlerts = selectedLog === 'alerts'
    ? (logData?.lines || [])
      .map(parseStructuredAlert)
      .filter((entry): entry is StructuredAlert => entry !== null)
    : [];
  const showStructuredAlerts = selectedLog === 'alerts' && structuredAlerts.length > 0;

  return (
    <div className="p-4 lg:p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl lg:text-3xl font-bold text-gray-900">System Logs</h1>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded"
              />
              Auto-refresh
            </label>
            <button
              onClick={() => fetchLogs(selectedLog)}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-2 mb-6 border-b border-gray-200">
          {logTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setSelectedLog(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-colors ${
                selectedLog === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              <tab.icon className="w-5 h-5" />
              <span className="font-medium">{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Log Content */}
        <div className="bg-white rounded-lg shadow-lg overflow-hidden">
          <div className="bg-gray-900 text-white p-4 font-mono text-sm">
            {logData?.message ? (
              <div className="text-yellow-400">{logData.message}</div>
            ) : showStructuredAlerts ? (
              <div className="space-y-3 font-sans text-sm">
                {structuredAlerts.map((entry, index) => {
                  const severity = entry.severity.toLowerCase();
                  const severityClass = severity === 'error'
                    ? 'bg-red-900/40 border-red-700 text-red-100'
                    : 'bg-yellow-900/40 border-yellow-700 text-yellow-100';
                  return (
                    <div
                      key={`${entry.ts}-${entry.event_type}-${index}`}
                      className={`border rounded-lg p-3 ${severityClass}`}
                    >
                      <div className="flex items-center justify-between gap-3 mb-1">
                        <span className="font-semibold">{entry.event_type}</span>
                        <span className="text-xs opacity-80">{formatAlertTimestamp(entry.ts)}</span>
                      </div>
                      <div className="text-sm">{entry.message}</div>
                      {entry.details && Object.keys(entry.details).length > 0 && (
                        <pre className="mt-2 text-xs bg-black/30 p-2 rounded overflow-x-auto">
                          {JSON.stringify(entry.details, null, 2)}
                        </pre>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : logData?.lines && logData.lines.length > 0 ? (
              <div className="space-y-1">
                {logData.lines.map((line, index) => {
                  // Color-code different log types
                  let className = 'text-gray-300';
                  if (line.includes('ALERT') || line.includes('ERROR')) {
                    className = 'text-red-400';
                  } else if (line.includes('WARN')) {
                    className = 'text-yellow-400';
                  } else if (line.includes('===')) {
                    className = 'text-blue-400 font-bold';
                  } else if (line.match(/\d{4}-\d{2}-\d{2}/)) {
                    className = 'text-green-400';
                  }

                  return (
                    <div key={index} className={className}>
                      {line}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-gray-500">No logs available</div>
            )}
          </div>
          {logData && logData.total_lines > 0 && (
            <div className="bg-gray-100 px-4 py-2 text-sm text-gray-600 border-t border-gray-200">
              Showing {logData.total_lines} log entries
            </div>
          )}
        </div>

        {/* Info Box */}
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-900">
              <p className="font-medium mb-1">About System Logs</p>
              <ul className="space-y-1 text-blue-800">
                <li><strong>System Health:</strong> Storage, temperature, power mode, CPU frequency, and API health checks</li>
                <li><strong>Alerts:</strong> Structured operator alerts from recording guardrails and stop/integrity outcomes</li>
                <li><strong>Watchdog:</strong> Recording health monitoring, including stalled pipelines and runtime anomalies</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
