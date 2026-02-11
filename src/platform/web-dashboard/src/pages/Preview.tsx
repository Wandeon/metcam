import React, { useState, useEffect } from 'react';
import { apiService, StatusResponseV3, PreviewStatus } from '@/services/api';
import { useWsChannel, useWsCommand } from '@/hooks/useWebSocket';
import { CameraPreview } from '@/components/CameraPreview';
import { Play, Square, AlertCircle, Eye } from 'lucide-react';

function transformPreviewStatus(raw: StatusResponseV3): PreviewStatus {
  const preview = raw.preview;
  return {
    status: preview.preview_active ? 'streaming' : 'idle',
    streaming: preview.preview_active,
    cam0_running: preview.cameras.camera_0.active,
    cam1_running: preview.cameras.camera_1.active,
    cam0_url: preview.cameras.camera_0.hls_url,
    cam1_url: preview.cameras.camera_1.hls_url,
    cam0_transport: preview.cameras.camera_0.transport || 'hls',
    cam1_transport: preview.cameras.camera_1.transport || 'hls',
    cam0_stream_kind: preview.cameras.camera_0.stream_kind || 'main_cam0',
    cam1_stream_kind: preview.cameras.camera_1.stream_kind || 'main_cam1',
    ice_servers: preview.ice_servers || [],
  };
}

async function fetchStatusRaw(): Promise<StatusResponseV3> {
  const response = await fetch('/api/v1/status', { cache: 'no-store' });
  return response.json();
}

function isWsTransportError(err: unknown): boolean {
  const message = err instanceof Error ? err.message : String(err ?? '');
  const normalized = message.toLowerCase();
  return normalized.includes('websocket not connected') || normalized.includes('websocket disconnected');
}

export const Preview: React.FC = () => {
  const [previewStatus, setPreviewStatus] = useState<PreviewStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [streamKey] = useState(0);
  const [isReloading] = useState(false);

  const { sendCommand, connected: wsConnected } = useWsCommand();

  // WS channel + REST fallback both return StatusResponseV3 shape
  const { data: wsStatusData } = useWsChannel<StatusResponseV3>(
    'status',
    fetchStatusRaw,
    2000,
  );

  // Process incoming data
  useEffect(() => {
    if (wsStatusData) {
      setLoading(false);
      setPreviewStatus(transformPreviewStatus(wsStatusData));
    }
  }, [wsStatusData]);

  // Initial fetch
  useEffect(() => {
    fetchStatusRaw().then(data => {
      setPreviewStatus(transformPreviewStatus(data));
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const handleStartPreview = async () => {
    setIsStarting(true);
    try {
      const startPreviewViaRest = async () => {
        const status = await apiService.getStatus();
        if (status.recording) {
          throw new Error('Cannot start preview while recording is active. Please stop recording first.');
        }
        await apiService.startPreview({ mode: 'normal', transport: 'webrtc' });
      };

      if (wsConnected) {
        try {
          await sendCommand('start_preview', { transport: 'webrtc' });
        } catch (err) {
          if (isWsTransportError(err)) {
            await startPreviewViaRest();
          } else {
            throw err;
          }
        }
      } else {
        await startPreviewViaRest();
      }
      await new Promise(resolve => setTimeout(resolve, 500));
    } catch (err: any) {
      setError(err.message || 'Failed to start preview');
      setTimeout(() => setError(null), 5000);
      console.error(err);
    } finally {
      setIsStarting(false);
    }
  };

  const handleStartCalibration = async () => {
    setIsStarting(true);
    try {
      const startCalibrationViaRest = async () => {
        const status = await apiService.getStatus();
        if (status.recording) {
          throw new Error('Cannot start calibration while recording is active. Please stop recording first.');
        }
        await apiService.startPreview({ mode: 'calibration', transport: 'webrtc' });
      };

      if (wsConnected) {
        try {
          await sendCommand('start_preview', { transport: 'webrtc' });
        } catch (err) {
          if (isWsTransportError(err)) {
            await startCalibrationViaRest();
          } else {
            throw err;
          }
        }
      } else {
        await startCalibrationViaRest();
      }
      await new Promise(resolve => setTimeout(resolve, 500));
    } catch (err: any) {
      setError(err.message || 'Failed to start calibration');
      setTimeout(() => setError(null), 5000);
      console.error(err);
    } finally {
      setIsStarting(false);
    }
  };

  const handleStopPreview = async () => {
    setIsStopping(true);
    try {
      const stopPreviewViaRest = async () => {
        await apiService.stopPreview();
      };

      if (wsConnected) {
        try {
          await sendCommand('stop_preview');
        } catch (err) {
          if (isWsTransportError(err)) {
            await stopPreviewViaRest();
          } else {
            throw err;
          }
        }
      } else {
        await stopPreviewViaRest();
      }
    } catch (err: any) {
      setError(err.message || 'Failed to stop preview');
      setTimeout(() => setError(null), 5000);
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
        <p className="text-gray-600 mt-1">Live preview - Same FOV as recording (GPU crop + barrel correction + rotation)</p>
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
              Start the preview stream to see what will be recorded. Preview shows the EXACT same field of view as your recordings.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <button
                onClick={handleStartPreview}
                disabled={isStarting}
                className="bg-green-500 hover:bg-green-600 disabled:bg-gray-400 text-white font-semibold py-3 rounded-lg transition-colors flex items-center justify-center"
              >
                <Play className="w-5 h-5 mr-2" />
                {isStarting ? 'Starting...' : 'Start Recording Preview'}
              </button>

              <button
                onClick={handleStartCalibration}
                disabled={isStarting}
                className="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white font-semibold py-3 rounded-lg transition-colors flex items-center justify-center"
              >
                <Eye className="w-5 h-5 mr-2" />
                {isStarting ? 'Starting...' : 'Start Calibration Stream'}
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-lg text-sm">
                <p className="font-semibold mb-2">Recording Preview:</p>
                <ul className="space-y-1 text-xs">
                  <li>• 2880x1620 @ 30fps</li>
                  <li>• GPU crop (56% FOV)</li>
                  <li>• Barrel correction + rotation</li>
                  <li>• SAME as recordings</li>
                </ul>
              </div>

              <div className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3 rounded-lg text-sm">
                <p className="font-semibold mb-2">Calibration Mode:</p>
                <ul className="space-y-1 text-xs">
                  <li>• Center 50% crop (1920x1080)</li>
                  <li>• 25% FOV @ 30fps</li>
                  <li>• 8 Mbps native 4K sharpness</li>
                  <li>• For focus check</li>
                </ul>
              </div>
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

      {isStreaming && previewStatus?.cam0_url && previewStatus?.cam1_url && !isReloading && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <CameraPreview
            key={`cam0-${streamKey}`}
            cameraId={0}
            streamUrl={previewStatus.cam0_url}
            title="Camera 0"
            resolution={(previewStatus as any).output_resolution || '1920x1080'}
            framerate={(previewStatus as any).framerate || 30}
            transport={previewStatus.cam0_transport}
            streamKind={previewStatus.cam0_stream_kind}
            iceServers={previewStatus.ice_servers?.map((s) => ({ urls: s.urls }))}
          />
          <CameraPreview
            key={`cam1-${streamKey}`}
            cameraId={1}
            streamUrl={previewStatus.cam1_url}
            title="Camera 1"
            resolution={(previewStatus as any).output_resolution || '1920x1080'}
            framerate={(previewStatus as any).framerate || 30}
            transport={previewStatus.cam1_transport}
            streamKind={previewStatus.cam1_stream_kind}
            iceServers={previewStatus.ice_servers?.map((s) => ({ urls: s.urls }))}
          />
        </div>
      )}

      {isStreaming && isReloading && (
        <div className="p-12 text-center bg-gray-100 rounded-lg">
          <div className="text-gray-600 text-lg mb-2">Applying new camera configuration...</div>
          <div className="text-gray-500 text-sm">Preview will restart in a moment</div>
        </div>
      )}

      {isStreaming && (
        <div className={`px-4 py-3 rounded-lg text-sm ${
          (previewStatus as any)?.mode === 'calibration'
            ? 'bg-blue-50 border border-blue-200 text-blue-800'
            : 'bg-yellow-50 border border-yellow-200 text-yellow-800'
        }`}>
          {(previewStatus as any)?.mode === 'calibration' ? (
            <>
              <p className="font-semibold mb-1">Calibration Mode Active:</p>
              <ul className="space-y-1">
                <li>• <strong>1920x1080 @ 30fps</strong> - Native 4K center crop (25% FOV)</li>
                <li>• <strong>8 Mbps</strong> - High quality encoding for maximum detail</li>
                <li>• <strong>Center 50% each axis</strong> - Native 4K pixels, 4x sharper than downscaled preview</li>
                <li>• Use this mode to fine-tune camera focus and check image quality</li>
                <li>• Stream will stop when you start recording</li>
              </ul>
            </>
          ) : (
            <>
              <p className="font-semibold mb-1">Recording Preview Active:</p>
              <ul className="space-y-1">
                <li>• <strong>2880x1620 @ 30fps</strong> - Same resolution as recordings</li>
                <li>• <strong>GPU crop (56% FOV)</strong> - Same field of view as recordings</li>
                <li>• <strong>Barrel correction + rotation</strong> - Same transformations as recordings</li>
                <li>• What you see is what gets recorded</li>
                <li>• Stream will stop automatically when you start recording</li>
              </ul>
            </>
          )}
        </div>
      )}

    </div>
  );
};
