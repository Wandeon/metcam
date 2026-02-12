import React, { useState, useEffect } from 'react';
import { CameraPreview } from '@/components/CameraPreview';
import { useWsChannel, useWsCommand } from '@/hooks/useWebSocket';
import {
  Layers,
  Camera,
  Activity,
  AlertCircle,
  CheckCircle,
  Clock,
  X,
  Video,
  Play,
  Square,
  Loader2,
  Trash2,
} from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

interface PanoramaStatus {
  preview_active: boolean;
  transport?: 'hls' | 'webrtc';
  stream_kind?: 'panorama';
  hls_url?: string;
  ice_servers?: Array<{ urls: string[]; username?: string; credential?: string }>;
  calibrated: boolean;
  calibration_date: string | null;
  quality_score: number | null;
  performance: {
    current_fps: number;
    avg_sync_drift_ms: number;
    dropped_frames: number;
  };
}

interface CalibrationStatus {
  is_calibrating: boolean;
  frames_captured: number;
  quality_score: number | null;
  calibrated: boolean;
  calibration_date: string | null;
}

interface ProcessingStatus {
  processing: boolean;
  progress: number;
  eta_seconds: number | null;
  completed: boolean;
  error: string | null;
}

interface Match {
  id: string;
  date: number;
}

// ============================================================================
// API Service
// ============================================================================

const panoramaApi = {
  async getStatus(): Promise<PanoramaStatus> {
    const response = await fetch('/api/v1/panorama/status');
    if (!response.ok) throw new Error('Failed to fetch panorama status');
    return response.json();
  },

  async getCalibrationStatus(): Promise<CalibrationStatus> {
    const response = await fetch('/api/v1/panorama/calibration');
    if (!response.ok) throw new Error('Failed to fetch calibration status');
    return response.json();
  },

  async startCalibration(): Promise<void> {
    const response = await fetch('/api/v1/panorama/calibration/start', {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to start calibration');
  },

  async captureFrame(): Promise<void> {
    const response = await fetch('/api/v1/panorama/calibration/capture', {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to capture frame');
  },

  async completeCalibration(): Promise<void> {
    const response = await fetch('/api/v1/panorama/calibration/complete', {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to complete calibration');
  },

  async resetCalibration(): Promise<void> {
    const response = await fetch('/api/v1/panorama/calibration/reset', {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to reset calibration');
  },

  async clearCalibration(): Promise<void> {
    const response = await fetch('/api/v1/panorama/calibration', {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to clear calibration');
  },

  async startPreview(): Promise<void> {
    const response = await fetch('/api/v1/panorama/preview/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transport: 'webrtc' }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to start preview');
    }
  },

  async stopPreview(): Promise<void> {
    const response = await fetch('/api/v1/panorama/preview/stop', {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to stop preview');
  },

  async processMatch(matchId: string): Promise<void> {
    const response = await fetch('/api/v1/panorama/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ match_id: matchId }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to start processing');
    }
  },

  async getProcessingStatus(matchId: string): Promise<ProcessingStatus> {
    const response = await fetch(`/api/v1/panorama/process/${matchId}/status`);
    if (!response.ok) throw new Error('Failed to fetch processing status');
    return response.json();
  },

  async getMatches(): Promise<Match[]> {
    const response = await fetch('/api/v1/recordings');
    if (!response.ok) throw new Error('Failed to fetch matches');
    const data = await response.json();

    const matches: Match[] = [];
    if (data.recordings) {
      Object.keys(data.recordings).forEach(matchId => {
        const createdAtRaw = data.recordings?.[matchId]?.created_at;
        const createdAtMs = typeof createdAtRaw === 'number'
          ? (createdAtRaw > 1e12 ? createdAtRaw : createdAtRaw * 1000)
          : 0;
        matches.push({
          id: matchId,
          date: createdAtMs,
        });
      });
    }

    return matches.sort((a, b) => b.date - a.date);
  },
};

// ============================================================================
// Main Component
// ============================================================================

export const Panorama: React.FC = () => {
  // State
  const [status, setStatus] = useState<PanoramaStatus | null>(null);
  const [calibrationStatus, setCalibrationStatus] = useState<CalibrationStatus | null>(null);
  const [calibrating, setCalibrating] = useState(false);
  const [capturedFrames, setCapturedFrames] = useState(0);
  const [previewActive, setPreviewActive] = useState(false);
  const [processingMatch, setProcessingMatch] = useState<string | null>(null);
  const [processingStatus, setProcessingStatus] = useState<ProcessingStatus | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [selectedMatch, setSelectedMatch] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionInProgress, setActionInProgress] = useState(false);

  // WS channel for combined panorama + calibration status
  const { data: wsPanoramaData } = useWsChannel<{ panorama: any; calibration: any }>(
    'panorama_status',
    async () => {
      // Fallback: fetch both via REST
      const [statusData, calData] = await Promise.all([
        panoramaApi.getStatus().catch(() => null),
        panoramaApi.getCalibrationStatus().catch(() => null),
      ]);
      return { panorama: statusData, calibration: calData } as any;
    },
    2000,
  );

  // Process WS panorama data
  useEffect(() => {
    if (wsPanoramaData) {
      if (wsPanoramaData.panorama) {
        setStatus(wsPanoramaData.panorama as PanoramaStatus);
      }
      if (wsPanoramaData.calibration) {
        setCalibrationStatus(wsPanoramaData.calibration as CalibrationStatus);
      }
      setLoading(false);
    }
  }, [wsPanoramaData]);

  // Initial fetch
  useEffect(() => {
    fetchStatus();
    fetchCalibrationStatus();
  }, []);

  // Fetch matches on mount
  useEffect(() => {
    fetchMatches();
  }, []);

  const { sendCommand, connected: wsConnected } = useWsCommand();

  // Poll processing status when active (WS command with REST fallback)
  useEffect(() => {
    if (!processingMatch) return;

    const pollProcessing = async () => {
      try {
        let status: ProcessingStatus;
        if (wsConnected) {
          try {
            status = await sendCommand('get_panorama_processing', { match_id: processingMatch });
          } catch {
            status = await panoramaApi.getProcessingStatus(processingMatch);
          }
        } else {
          status = await panoramaApi.getProcessingStatus(processingMatch);
        }
        setProcessingStatus(status);

        if (status.completed) {
          setSuccess(`Processing completed for ${processingMatch}`);
          setTimeout(() => {
            setSuccess(null);
            setProcessingMatch(null);
            setProcessingStatus(null);
          }, 5000);
        } else if (status.error) {
          setError(status.error);
          setTimeout(() => setError(null), 5000);
          setProcessingMatch(null);
          setProcessingStatus(null);
        }
      } catch (err) {
        console.error('Failed to fetch processing status:', err);
      }
    };

    pollProcessing();
    const interval = setInterval(pollProcessing, 5000);
    return () => clearInterval(interval);
  }, [processingMatch, wsConnected]);

  // Sync local state with fetched status
  useEffect(() => {
    if (status) {
      setPreviewActive(status.preview_active);
    }
  }, [status]);

  useEffect(() => {
    if (calibrationStatus) {
      setCalibrating(calibrationStatus.is_calibrating);
      setCapturedFrames(calibrationStatus.frames_captured);
    }
  }, [calibrationStatus]);

  const fetchStatus = async () => {
    try {
      const data = await panoramaApi.getStatus();
      setStatus(data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch status:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchCalibrationStatus = async () => {
    try {
      const data = await panoramaApi.getCalibrationStatus();
      setCalibrationStatus(data);
    } catch (err) {
      console.error('Failed to fetch calibration status:', err);
    }
  };

  const fetchMatches = async () => {
    try {
      const data = await panoramaApi.getMatches();
      setMatches(data);
      if (data.length > 0 && !selectedMatch) {
        setSelectedMatch(data[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch matches:', err);
    }
  };

  const showError = (message: string) => {
    setError(message);
    setTimeout(() => setError(null), 5000);
  };

  const showSuccess = (message: string) => {
    setSuccess(message);
    setTimeout(() => setSuccess(null), 3000);
  };

  // ========================================================================
  // Calibration Handlers
  // ========================================================================

  const handleStartCalibration = async () => {
    setActionInProgress(true);
    try {
      await panoramaApi.startCalibration();
      showSuccess('Calibration started');
      await fetchCalibrationStatus();
    } catch (err) {
      showError('Failed to start calibration');
      console.error(err);
    } finally {
      setActionInProgress(false);
    }
  };

  const handleCaptureFrame = async () => {
    setActionInProgress(true);
    try {
      await panoramaApi.captureFrame();
      showSuccess('Frame captured');
      await fetchCalibrationStatus();
    } catch (err) {
      showError('Failed to capture frame');
      console.error(err);
    } finally {
      setActionInProgress(false);
    }
  };

  const handleCompleteCalibration = async () => {
    setActionInProgress(true);
    try {
      await panoramaApi.completeCalibration();
      showSuccess('Calibration completed successfully!');
      await fetchCalibrationStatus();
      await fetchStatus();
    } catch (err) {
      showError('Failed to complete calibration');
      console.error(err);
    } finally {
      setActionInProgress(false);
    }
  };

  const handleResetCalibration = async () => {
    if (!confirm('Are you sure you want to reset calibration? All captured frames will be lost.')) {
      return;
    }

    setActionInProgress(true);
    try {
      await panoramaApi.resetCalibration();
      showSuccess('Calibration reset successfully');
      await fetchCalibrationStatus();
    } catch (err) {
      showError('Failed to reset calibration');
      console.error(err);
    } finally {
      setActionInProgress(false);
    }
  };

  const handleClearCalibration = async () => {
    if (!confirm('Are you sure you want to clear the calibration data?')) {
      return;
    }

    setActionInProgress(true);
    try {
      await panoramaApi.clearCalibration();
      showSuccess('Calibration data cleared');
      await fetchCalibrationStatus();
      await fetchStatus();
    } catch (err) {
      showError('Failed to clear calibration');
      console.error(err);
    } finally {
      setActionInProgress(false);
    }
  };

  // ========================================================================
  // Preview Handlers
  // ========================================================================

  const handleStartPreview = async () => {
    setActionInProgress(true);
    try {
      await panoramaApi.startPreview();
      showSuccess('Preview started');
      await fetchStatus();
    } catch (err: any) {
      showError(err.message || 'Failed to start preview');
      console.error(err);
    } finally {
      setActionInProgress(false);
    }
  };

  const handleStopPreview = async () => {
    setActionInProgress(true);
    try {
      await panoramaApi.stopPreview();
      showSuccess('Preview stopped');
      await fetchStatus();
    } catch (err) {
      showError('Failed to stop preview');
      console.error(err);
    } finally {
      setActionInProgress(false);
    }
  };

  // ========================================================================
  // Processing Handlers
  // ========================================================================

  const handleProcessMatch = async () => {
    if (!selectedMatch) {
      showError('Please select a match to process');
      return;
    }

    if (!confirm(`Start processing panorama for ${selectedMatch}?`)) {
      return;
    }

    setActionInProgress(true);
    try {
      await panoramaApi.processMatch(selectedMatch);
      setProcessingMatch(selectedMatch);
      showSuccess(`Processing started for ${selectedMatch}`);
    } catch (err: any) {
      showError(err.message || 'Failed to start processing');
      console.error(err);
    } finally {
      setActionInProgress(false);
    }
  };

  // ========================================================================
  // Format Helpers
  // ========================================================================

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return 'Never';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return 'Unknown';
    }
  };

  const formatETA = (seconds: number | null): string => {
    if (!seconds) return 'Unknown';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (mins > 0) {
      return `${mins}m ${secs}s`;
    }
    return `${secs}s`;
  };

  // ========================================================================
  // Render
  // ========================================================================

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse">Loading panorama status...</div>
      </div>
    );
  }

  const isCalibrated = status?.calibrated || false;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Panorama Stitching</h1>
        <p className="text-gray-600 mt-1">GPU-accelerated panorama preview and post-processing</p>
      </div>

      {/* Notifications */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg flex items-center justify-between">
          <div className="flex items-center">
            <AlertCircle className="w-5 h-5 mr-2" />
            {error}
          </div>
          <button onClick={() => setError(null)} className="text-red-600 hover:text-red-800">
            <X className="w-5 h-5" />
          </button>
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg flex items-center justify-between">
          <div className="flex items-center">
            <CheckCircle className="w-5 h-5 mr-2" />
            {success}
          </div>
          <button onClick={() => setSuccess(null)} className="text-green-700 hover:text-green-900">
            <X className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Status Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Calibration Status Card */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Calibration</p>
              <p className="text-2xl font-bold mt-1">
                {isCalibrated ? (
                  <span className="text-green-600">Calibrated</span>
                ) : (
                  <span className="text-yellow-600">Not Calibrated</span>
                )}
              </p>
              {isCalibrated && status?.quality_score && (
                <p className="text-sm text-gray-500 mt-1">
                  Quality: {(status.quality_score * 100).toFixed(1)}%
                </p>
              )}
            </div>
            {isCalibrated ? (
              <CheckCircle className="w-8 h-8 text-green-500" />
            ) : (
              <AlertCircle className="w-8 h-8 text-yellow-500" />
            )}
          </div>
        </div>

        {/* Preview Status Card */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Preview</p>
              <p className="text-2xl font-bold mt-1">
                {previewActive ? (
                  <span className="text-green-600">Active</span>
                ) : (
                  <span className="text-gray-400">Inactive</span>
                )}
              </p>
              {previewActive && status?.performance && (
                <p className="text-sm text-gray-500 mt-1">
                  {status.performance.current_fps.toFixed(1)} FPS
                </p>
              )}
            </div>
            {previewActive ? (
              <Video className="w-8 h-8 text-green-500 animate-pulse" />
            ) : (
              <Video className="w-8 h-8 text-gray-400" />
            )}
          </div>
        </div>

        {/* Performance Stats Card */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <p className="text-sm text-gray-600">Performance</p>
              {status?.performance ? (
                <div className="mt-2 space-y-1">
                  <p className="text-sm text-gray-700">
                    Sync: {status.performance.avg_sync_drift_ms.toFixed(1)}ms
                  </p>
                  <p className="text-sm text-gray-700">
                    Dropped: {status.performance.dropped_frames}
                  </p>
                </div>
              ) : (
                <p className="text-sm text-gray-400 mt-2">No data</p>
              )}
            </div>
            <Activity className="w-8 h-8 text-blue-500" />
          </div>
        </div>
      </div>

      {/* Calibration Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center">
            <Camera className="w-6 h-6 mr-2 text-blue-600" />
            Calibration
          </h2>
          {isCalibrated && (
            <button
              onClick={handleClearCalibration}
              disabled={actionInProgress || previewActive}
              className="flex items-center px-3 py-2 bg-red-500 hover:bg-red-600 disabled:bg-gray-400 text-white text-sm rounded-lg transition-colors"
            >
              <Trash2 className="w-4 h-4 mr-1" />
              Clear
            </button>
          )}
        </div>

        {!isCalibrated && !calibrating && (
          <div>
            <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-lg mb-4">
              <div className="flex items-center">
                <AlertCircle className="w-5 h-5 mr-2" />
                <div>
                  <p className="font-semibold">Calibration Required</p>
                  <p className="text-sm mt-1">
                    Panorama stitching requires calibration to align the two camera views.
                    This only needs to be done once (unless cameras are moved).
                  </p>
                </div>
              </div>
            </div>
            <button
              onClick={handleStartCalibration}
              disabled={actionInProgress}
              className="w-full bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white font-semibold py-3 rounded-lg transition-colors"
            >
              Start Calibration
            </button>
          </div>
        )}

        {calibrating && (
          <div className="space-y-4">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <p className="font-semibold text-blue-900 mb-2">Calibration in Progress</p>
              <p className="text-sm text-blue-700 mb-3">
                Capture 10+ frames with good overlap between cameras.
                Move slowly to cover different angles of the overlap region.
              </p>

              {/* Progress Bar */}
              <div className="mb-3">
                <div className="flex items-center justify-between text-sm text-blue-800 mb-1">
                  <span>Frames captured</span>
                  <span className="font-bold">{capturedFrames} / 10</span>
                </div>
                <div className="w-full bg-blue-200 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                    style={{ width: `${Math.min((capturedFrames / 10) * 100, 100)}%` }}
                  />
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex gap-3">
                <button
                  onClick={handleCaptureFrame}
                  disabled={actionInProgress}
                  className="flex-1 bg-green-500 hover:bg-green-600 disabled:bg-gray-400 text-white font-semibold py-3 rounded-lg transition-colors"
                >
                  Capture Frame
                </button>
                <button
                  onClick={handleCompleteCalibration}
                  disabled={actionInProgress || capturedFrames < 10}
                  className="flex-1 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white font-semibold py-3 rounded-lg transition-colors"
                >
                  Complete Calibration
                </button>
              </div>
              <button
                onClick={handleResetCalibration}
                disabled={actionInProgress}
                className="w-full bg-red-500 hover:bg-red-600 disabled:bg-gray-400 text-white font-semibold py-2 rounded-lg transition-colors"
              >
                Reset Calibration
              </button>
            </div>
          </div>
        )}

        {isCalibrated && !calibrating && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-center mb-2">
              <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
              <p className="font-semibold text-green-900">System Calibrated</p>
            </div>
            <div className="text-sm text-green-800 space-y-1">
              {status?.quality_score && (
                <p>Quality Score: {(status.quality_score * 100).toFixed(1)}%</p>
              )}
              {status?.calibration_date && (
                <p>Calibrated: {formatDate(status.calibration_date)}</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Preview Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4 flex items-center">
          <Layers className="w-6 h-6 mr-2 text-purple-600" />
          Panorama Preview
        </h2>

        {!isCalibrated ? (
          <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-lg">
            <div className="flex items-center">
              <AlertCircle className="w-5 h-5 mr-2" />
              <p>Preview requires calibration. Complete calibration first.</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex gap-3">
              {!previewActive ? (
                <button
                  onClick={handleStartPreview}
                  disabled={actionInProgress}
                  className="flex items-center px-6 py-3 bg-green-500 hover:bg-green-600 disabled:bg-gray-400 text-white font-semibold rounded-lg transition-colors"
                >
                  <Play className="w-5 h-5 mr-2" />
                  Start Preview
                </button>
              ) : (
                <button
                  onClick={handleStopPreview}
                  disabled={actionInProgress}
                  className="flex items-center px-6 py-3 bg-red-500 hover:bg-red-600 disabled:bg-gray-400 text-white font-semibold rounded-lg transition-colors"
                >
                  <Square className="w-5 h-5 mr-2" />
                  Stop Preview
                </button>
              )}
            </div>

            {previewActive && (
              <div className="space-y-4">
                {/* Preview Stream */}
                <CameraPreview
                  cameraId={-1}
                  streamUrl={status?.hls_url || '/hls/panorama.m3u8'}
                  title="Panorama Preview"
                  resolution="3840x1315"
                  framerate={status?.performance?.current_fps || 15}
                  transport={status?.transport || 'hls'}
                  streamKind={(status?.stream_kind as any) || 'panorama'}
                  iceServers={status?.ice_servers?.map((s) => ({
                    urls: s.urls,
                    username: s.username,
                    credential: s.credential,
                  }))}
                />

                {/* Performance Metrics */}
                {status?.performance && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-600">Frame Rate</p>
                      <p className="text-2xl font-bold text-gray-900">
                        {status.performance.current_fps.toFixed(1)} FPS
                      </p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-600">Sync Drift</p>
                      <p className="text-2xl font-bold text-gray-900">
                        {status.performance.avg_sync_drift_ms.toFixed(1)} ms
                      </p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-600">Dropped Frames</p>
                      <p className="text-2xl font-bold text-gray-900">
                        {status.performance.dropped_frames}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Post-Processing Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4 flex items-center">
          <Clock className="w-6 h-6 mr-2 text-orange-600" />
          Post-Processing
        </h2>

        <div className="space-y-4">
          <div>
            <label htmlFor="matchSelect" className="block text-sm font-medium text-gray-700 mb-2">
              Select Match to Process
            </label>
            <select
              id="matchSelect"
              value={selectedMatch}
              onChange={(e) => setSelectedMatch(e.target.value)}
              disabled={!!processingMatch || matches.length === 0}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:text-gray-500"
            >
              {matches.length === 0 ? (
                <option value="">No matches available</option>
              ) : (
                matches.map((match) => (
                  <option key={match.id} value={match.id}>
                    {match.id}
                  </option>
                ))
              )}
            </select>
          </div>

          {processingMatch && processingStatus && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center mb-3">
                <Loader2 className="w-5 h-5 text-blue-600 animate-spin mr-2" />
                <p className="font-semibold text-blue-900">
                  Processing: {processingMatch}
                </p>
              </div>

              {/* Progress Bar */}
              <div className="mb-3">
                <div className="flex items-center justify-between text-sm text-blue-800 mb-1">
                  <span>Progress</span>
                  <span className="font-bold">{processingStatus.progress}%</span>
                </div>
                <div className="w-full bg-blue-200 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-blue-600 h-3 rounded-full transition-all duration-500"
                    style={{ width: `${processingStatus.progress}%` }}
                  />
                </div>
              </div>

              {processingStatus.eta_seconds !== null && (
                <p className="text-sm text-blue-700">
                  Estimated time remaining: {formatETA(processingStatus.eta_seconds)}
                </p>
              )}
            </div>
          )}

          <button
            onClick={handleProcessMatch}
            disabled={
              actionInProgress ||
              !selectedMatch ||
              !!processingMatch ||
              !isCalibrated ||
              matches.length === 0
            }
            className="w-full bg-orange-500 hover:bg-orange-600 disabled:bg-gray-400 text-white font-semibold py-3 rounded-lg transition-colors"
          >
            {processingMatch ? 'Processing...' : 'Process Match'}
          </button>

          <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600">
            <p className="font-semibold mb-2">Post-Processing Information:</p>
            <ul className="space-y-1 list-disc list-inside">
              <li>Processes all segments from both cameras</li>
              <li>Creates a single panorama video file</li>
              <li>Resolution: 3840x1315 (double-wide panorama)</li>
              <li>Uses GPU-accelerated VPI stitching</li>
              <li>Typical processing time: 1-2x recording duration</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
