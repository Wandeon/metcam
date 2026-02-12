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

function assertCommandSuccess(result: any, fallbackMessage: string): void {
  if (result && typeof result === 'object' && result.success === false) {
    throw new Error(result.message || fallbackMessage);
  }
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
        const result = await apiService.startPreview({ transport: 'webrtc' });
        if (result.status !== 'started') {
          throw new Error('Failed to start preview');
        }
      };

      if (wsConnected) {
        try {
          const result = await sendCommand('start_preview', { transport: 'webrtc' });
          assertCommandSuccess(result, 'Failed to start preview');
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

  const handleStopPreview = async () => {
    setIsStopping(true);
    try {
      const stopPreviewViaRest = async () => {
        const result = await apiService.stopPreview();
        if (result.status !== 'stopped') {
          throw new Error('Failed to stop preview');
        }
      };

      if (wsConnected) {
        try {
          const result = await sendCommand('stop_preview');
          assertCommandSuccess(result, 'Failed to stop preview');
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
  const cam0Transport = previewStatus?.cam0_transport;
  const cam1Transport = previewStatus?.cam1_transport;
  const transportLabel =
    cam0Transport && cam1Transport
      ? cam0Transport === cam1Transport
        ? cam0Transport.toUpperCase()
        : `${cam0Transport.toUpperCase()} / ${cam1Transport.toUpperCase()}`
      : 'N/A';

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Camera Preview</h1>
        <p className="text-gray-600 mt-1">Live preview transport and stream health for both cameras</p>
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
              Start preview to validate camera feeds before recording. Recording and preview remain mutually exclusive.
            </p>

            <div className="grid grid-cols-1 gap-4">
              <button
                onClick={handleStartPreview}
                disabled={isStarting}
                className="bg-green-500 hover:bg-green-600 disabled:bg-gray-400 text-white font-semibold py-3 rounded-lg transition-colors flex items-center justify-center"
              >
                <Play className="w-5 h-5 mr-2" />
                {isStarting ? 'Starting...' : 'Start Preview'}
              </button>
            </div>

            <div className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3 rounded-lg text-sm">
              <p className="font-semibold mb-1">Calibration workflow moved</p>
              <p>Use the Panorama page for calibration and stitching controls.</p>
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
          cam0Transport === 'webrtc' || cam1Transport === 'webrtc'
            ? 'bg-green-50 border border-green-200 text-green-800'
            : 'bg-yellow-50 border border-yellow-200 text-yellow-800'
        }`}>
          <p className="font-semibold mb-1">Live Preview Active</p>
          <ul className="space-y-1">
            <li>• Transport: <strong>{transportLabel}</strong></li>
            <li>• Camera 0 stream: <strong>{previewStatus?.cam0_running ? 'active' : 'inactive'}</strong></li>
            <li>• Camera 1 stream: <strong>{previewStatus?.cam1_running ? 'active' : 'inactive'}</strong></li>
            <li>• Preview will stop automatically when recording starts</li>
          </ul>
        </div>
      )}

    </div>
  );
};
