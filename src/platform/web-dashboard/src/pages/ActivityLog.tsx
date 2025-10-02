import React, { useState, useEffect } from 'react';
import { Activity, Download, RefreshCw, AlertTriangle, Info, XCircle, Play, Square, Cog, CheckCircle, Upload, CloudUpload } from 'lucide-react';

interface ActivityEvent {
  id: number;
  event_type: string;
  component: string;
  severity: string;
  match_id: string | null;
  details: string | null;
  timestamp: string;
}

export const ActivityLog: React.FC = () => {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({
    event_type: '',
    severity: '',
    limit: 100
  });

  useEffect(() => {
    loadEvents();
    const interval = setInterval(loadEvents, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, [filter]);

  const loadEvents = async () => {
    try {
      const params = new URLSearchParams();
      if (filter.event_type) params.append('event_type', filter.event_type);
      if (filter.severity) params.append('severity', filter.severity);
      params.append('limit', filter.limit.toString());

      const response = await fetch(`/api/v1/activity/?${params}`);
      const data = await response.json();
      setEvents(data.events || []);
    } catch (error) {
      console.error('Failed to load activity log:', error);
    } finally {
      setLoading(false);
    }
  };

  const exportLog = async (format: string) => {
    window.open(`/api/v1/activity/export?format=${format}`, '_blank');
  };

  const getEventIcon = (event_type: string, severity: string) => {
    // Show severity icons for errors/warnings
    if (severity === 'error' || severity === 'critical') {
      return <XCircle className="w-5 h-5 text-red-500" />;
    }
    if (severity === 'warning') {
      return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
    }

    // Event-specific icons for normal events
    switch (event_type) {
      case 'recording_started':
        return <Play className="w-5 h-5 text-green-600" />;
      case 'recording_stopped':
        return <Square className="w-5 h-5 text-red-600" />;
      case 'processing_started':
        return <Cog className="w-5 h-5 text-blue-600 animate-spin" />;
      case 'processing_completed':
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      case 'upload_started':
        return <Upload className="w-5 h-5 text-purple-600" />;
      case 'upload_completed':
        return <CloudUpload className="w-5 h-5 text-green-600" />;
      default:
        return <Info className="w-5 h-5 text-blue-500" />;
    }
  };

  const getSeverityBg = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-100 border-red-300';
      case 'error':
        return 'bg-red-50 border-red-200';
      case 'warning':
        return 'bg-yellow-50 border-yellow-200';
      default:
        return 'bg-white border-gray-200';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString('hr-HR');
  };

  return (
    <div className="p-4 md:p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold flex items-center">
          <Activity className="w-6 h-6 mr-2" />
          Activity Log
        </h1>
        <div className="flex gap-2">
          <button
            onClick={() => exportLog('csv')}
            className="flex items-center px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 touch-manipulation"
          >
            <Download className="w-4 h-4 mr-2" />
            Export CSV
          </button>
          <button
            onClick={loadEvents}
            className="flex items-center px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 touch-manipulation"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-4">
        <div className="flex flex-wrap gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Event Type</label>
            <select
              value={filter.event_type}
              onChange={(e) => setFilter({ ...filter, event_type: e.target.value })}
              className="px-3 py-2 border rounded"
            >
              <option value="">All Events</option>
              <option value="recording_started">Recording Started</option>
              <option value="recording_stopped">Recording Stopped</option>
              <option value="processing_started">Processing Started</option>
              <option value="processing_completed">Processing Completed</option>
              <option value="upload_started">Upload Started</option>
              <option value="upload_completed">Upload Completed</option>
              <option value="error">Errors</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Severity</label>
            <select
              value={filter.severity}
              onChange={(e) => setFilter({ ...filter, severity: e.target.value })}
              className="px-3 py-2 border rounded"
            >
              <option value="">All Severities</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
              <option value="critical">Critical</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Limit</label>
            <select
              value={filter.limit}
              onChange={(e) => setFilter({ ...filter, limit: parseInt(e.target.value) })}
              className="px-3 py-2 border rounded"
            >
              <option value="50">50 events</option>
              <option value="100">100 events</option>
              <option value="200">200 events</option>
              <option value="500">500 events</option>
            </select>
          </div>
        </div>
      </div>

      {/* Activity Events */}
      <div className="space-y-2">
        {loading && (
          <div className="text-center py-8 text-gray-500">Loading activity log...</div>
        )}

        {!loading && events.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <Activity className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <p>No activity events found</p>
          </div>
        )}

        {!loading && events.map((event) => {
          const details = event.details ? JSON.parse(event.details) : {};
          const getEventSummary = () => {
            switch (event.event_type) {
              case 'recording_started':
                return `Started recording`;
              case 'recording_stopped':
                const duration = details.duration_seconds || 0;
                const size = details.file_size_bytes ? (details.file_size_bytes / (1024**3)).toFixed(2) : 0;
                return `Stopped recording (${duration}s, ${size}GB)`;
              case 'processing_started':
                return `Started ${details.job_type || 'processing'}`;
              case 'processing_completed':
                return `Processing complete - ${details.output_file?.split('/').pop() || 'output ready'}`;
              case 'upload_started':
                return `Uploading to ${details.destination?.split('/')[0] || 'server'}...`;
              case 'upload_completed':
                const speed = details.speed_mbps || 0;
                const uploadDuration = details.duration_seconds || 0;
                return `Upload complete (${speed} Mbps, ${uploadDuration}s)`;
              case 'error':
                return `Error: ${details.error || 'Unknown error'}`;
              default:
                return event.event_type.replace(/_/g, ' ');
            }
          };

          return (
            <div
              key={event.id}
              className={`border rounded-lg p-3 ${getSeverityBg(event.severity)}`}
            >
              <div className="flex items-center gap-3">
                {getEventIcon(event.event_type, event.severity)}
                <div className="flex-1 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-medium text-gray-600">
                      {formatTimestamp(event.timestamp)}
                    </span>
                    <span className="font-semibold">
                      {event.match_id || 'System'}
                    </span>
                    <span className="text-sm text-gray-700">
                      {getEventSummary()}
                    </span>
                  </div>
                  <span className="text-xs text-gray-500 uppercase">
                    {event.component}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
