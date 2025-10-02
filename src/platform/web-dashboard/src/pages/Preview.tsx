import React, { useState, useEffect } from 'react';
import { apiService } from '@/services/api';
import { CameraPreview } from '@/components/CameraPreview';
import { Play, Square, AlertCircle, Eye } from 'lucide-react';

export const Preview: React.FC = () => {
  const [previewStatus, setPreviewStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  const fetchPreviewStatus = async () => {
    try {
      const data = await apiService.getPreviewStatus();
      setPreviewStatus(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch preview status');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPreviewStatus();
    const interval = setInterval(fetchPreviewStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleStartPreview = async () => {
    setIsStarting(true);
    try {
      await apiService.startPreview();
      await fetchPreviewStatus();
    } catch (err) {
      alert('Failed to start preview');
      console.error(err);
    } finally {
      setIsStarting(false);
    }
  };

  const handleStopPreview = async () => {
    setIsStopping(true);
    try {
      await apiService.stopPreview();
      await fetchPreviewStatus();
    } catch (err) {
      alert('Failed to stop preview');
      console.error(err);
    } finally {
      setIsStopping(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse">Loading...</div>
      </div>
    );
  }

  const isStreaming = previewStatus?.streaming;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Camera Preview</h1>
        <p className="text-gray-600 mt-1">HD live preview (1280x720 @ 10fps)</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg flex items-center">
          <AlertCircle className="w-5 h-5 mr-2" />
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center">
            <Eye className="w-6 h-6 text-gray-700 mr-2" />
            <h2 className="text-xl font-semibold">Preview Control</h2>
          </div>

          {isStreaming ? (
            <div className="flex items-center">
              <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse mr-2" />
              <span className="text-green-600 font-medium">Streaming</span>
            </div>
          ) : (
            <span className="text-gray-500">Not streaming</span>
          )}
        </div>

        {!isStreaming ? (
          <div className="space-y-4">
            <p className="text-sm text-gray-600">
              Start the preview stream to see live camera feeds at Full HD resolution.
              This allows you to verify camera positioning, focus, and lighting before recording.
            </p>

            <button
              onClick={handleStartPreview}
              disabled={isStarting}
              className="w-full bg-green-500 hover:bg-green-600 disabled:bg-gray-400 text-white font-semibold py-3 rounded-lg transition-colors flex items-center justify-center"
            >
              <Play className="w-5 h-5 mr-2" />
              {isStarting ? 'Starting Preview...' : 'Start Preview Stream'}
            </button>

            <div className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3 rounded-lg text-sm">
              <p className="font-semibold mb-1">Preview Settings:</p>
              <ul className="space-y-1">
                <li>• Resolution: 1280x720 (HD)</li>
                <li>• Frame rate: 10 fps</li>
                <li>• Bitrate: 3 Mbps per camera</li>
                <li>• Format: HLS stream (H.264)</li>
              </ul>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <button
              onClick={handleStopPreview}
              disabled={isStopping}
              className="w-full bg-red-500 hover:bg-red-600 disabled:bg-gray-400 text-white font-semibold py-3 rounded-lg transition-colors flex items-center justify-center"
            >
              <Square className="w-5 h-5 mr-2" />
              {isStopping ? 'Stopping...' : 'Stop Preview Stream'}
            </button>
          </div>
        )}
      </div>

      {isStreaming && previewStatus?.cam0_url && previewStatus?.cam1_url && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <CameraPreview
            cameraId={0}
            streamUrl={previewStatus.cam0_url}
            title="Camera 0"
          />
          <CameraPreview
            cameraId={1}
            streamUrl={previewStatus.cam1_url}
            title="Camera 1"
          />
        </div>
      )}

      {isStreaming && (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-lg text-sm">
          <p className="font-semibold mb-1">⚠️ Important Notes:</p>
          <ul className="space-y-1">
            <li>• Preview stream uses Full HD (1920x1080) at 30fps</li>
            <li>• Stop preview before starting recording to free camera resources</li>
            <li>• Preview has ~2-4 second latency (normal for HLS)</li>
            <li>• Remove lens caps and ensure adequate lighting</li>
          </ul>
        </div>
      )}
    </div>
  );
};
