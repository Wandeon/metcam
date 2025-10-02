import React, { useState, useEffect } from 'react';
import { apiService, RecordingStatus } from '@/services/api';
import { Video, AlertCircle, CheckCircle, Clock } from 'lucide-react';

export const Dashboard: React.FC = () => {
  const [status, setStatus] = useState<RecordingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [matchId, setMatchId] = useState('');
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  const fetchStatus = async () => {
    try {
      const data = await apiService.getStatus();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch status');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleStartRecording = async () => {
    if (!matchId.trim()) {
      alert('Please enter a match ID');
      return;
    }

    setIsStarting(true);
    try {
      await apiService.startRecording({
        match_id: matchId,
        resolution: '3840x2160',
        fps: 22,
        bitrate: 100000,
      });
      await fetchStatus();
      setMatchId('');
    } catch (err) {
      alert('Failed to start recording');
      console.error(err);
    } finally {
      setIsStarting(false);
    }
  };

  const handleStopRecording = async () => {
    setIsStopping(true);
    try {
      const result = await apiService.stopRecording();
      await fetchStatus();
      alert(`Recording stopped. Duration: ${Math.round(result.duration_seconds)}s`);
    } catch (err) {
      alert('Failed to stop recording');
      console.error(err);
    } finally {
      setIsStopping(false);
    }
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse">Loading...</div>
      </div>
    );
  }

  const isRecording = status?.status === 'recording';

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-1">Control dual camera recording</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg flex items-center">
          <AlertCircle className="w-5 h-5 mr-2" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Status</p>
              <p className="text-2xl font-bold mt-1">
                {isRecording ? (
                  <span className="text-red-600">Recording</span>
                ) : (
                  <span className="text-gray-600">Idle</span>
                )}
              </p>
            </div>
            {isRecording ? (
              <div className="w-4 h-4 bg-red-600 rounded-full animate-pulse" />
            ) : (
              <CheckCircle className="w-8 h-8 text-green-500" />
            )}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Camera 0</p>
              <p className="text-2xl font-bold mt-1">
                {status?.cam0_running ? (
                  <span className="text-green-600">Active</span>
                ) : (
                  <span className="text-gray-400">Inactive</span>
                )}
              </p>
            </div>
            <Video className={`w-8 h-8 ${status?.cam0_running ? 'text-green-500' : 'text-gray-400'}`} />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Camera 1</p>
              <p className="text-2xl font-bold mt-1">
                {status?.cam1_running ? (
                  <span className="text-green-600">Active</span>
                ) : (
                  <span className="text-gray-400">Inactive</span>
                )}
              </p>
            </div>
            <Video className={`w-8 h-8 ${status?.cam1_running ? 'text-green-500' : 'text-gray-400'}`} />
          </div>
        </div>
      </div>

      {isRecording && status?.duration_seconds !== undefined && (
        <div className="bg-gradient-to-r from-red-500 to-red-600 text-white rounded-lg shadow-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm opacity-90">Recording Duration</p>
              <p className="text-4xl font-bold mt-1">{formatDuration(status.duration_seconds)}</p>
              <p className="text-sm opacity-90 mt-2">Match ID: {status.match_id}</p>
            </div>
            <Clock className="w-12 h-12 opacity-90" />
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Recording Control</h2>

        {!isRecording ? (
          <div className="space-y-4">
            <div>
              <label htmlFor="matchId" className="block text-sm font-medium text-gray-700 mb-2">
                Match ID
              </label>
              <input
                type="text"
                id="matchId"
                value={matchId}
                onChange={(e) => setMatchId(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                placeholder="e.g., match_20251002_001"
              />
            </div>

            <button
              onClick={handleStartRecording}
              disabled={isStarting || !matchId.trim()}
              className="w-full bg-green-500 hover:bg-green-600 disabled:bg-gray-400 text-white font-semibold py-3 rounded-lg transition-colors"
            >
              {isStarting ? 'Starting...' : 'Start Recording'}
            </button>

            <div className="text-sm text-gray-600 bg-gray-50 p-4 rounded-lg">
              <p className="font-semibold mb-2">Recording Settings:</p>
              <ul className="space-y-1">
                <li>• Resolution: 3840x2160 (4K) @ 22fps constant</li>
                <li>• Encoder: H.264 (x264 software, ultrafast preset)</li>
                <li>• Bitrate: ~50 Mbps per camera (~100 Mbps total)</li>
                <li>• Sports mode: 1/250s min shutter, ISO ≤1600</li>
                <li>• Storage: ~165 GB per 150min match (both cameras)</li>
              </ul>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-lg">
              <p className="font-semibold">Recording in progress</p>
              <p className="text-sm mt-1">Click "Stop Recording" to finalize the video files</p>
            </div>

            <button
              onClick={handleStopRecording}
              disabled={isStopping}
              className="w-full bg-red-500 hover:bg-red-600 disabled:bg-gray-400 text-white font-semibold py-3 rounded-lg transition-colors"
            >
              {isStopping ? 'Stopping...' : 'Stop Recording'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
