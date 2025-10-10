import React, { useEffect, useRef, useState } from 'react';
import Hls from 'hls.js';
import { Video, AlertCircle, Maximize2, ZoomIn, ZoomOut, RotateCcw, X, ChevronUp, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react';

interface CameraPreviewProps {
  cameraId: number;
  streamUrl: string;
  title: string;
}

export const CameraPreview: React.FC<CameraPreviewProps> = ({
  streamUrl,
  title,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const hlsRef = useRef<Hls | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    setLoading(true);
    setError(null);

    console.log('Loading HLS stream:', streamUrl);

    // Check if HLS is supported
    if (Hls.isSupported()) {
      const hls = new Hls({
        enableWorker: true,
        lowLatencyMode: true,
        backBufferLength: 3,  // Keep minimal back buffer for low latency
        maxBufferLength: 4,   // Small forward buffer (4 seconds with 1s segments)
        maxMaxBufferLength: 8,
        maxBufferSize: 10 * 1000 * 1000,
        maxBufferHole: 0.2,
        liveSyncDurationCount: 1,  // Play 1 segment behind live edge
        liveMaxLatencyDurationCount: 3,  // Max 3 segments behind
        manifestLoadingMaxRetry: 6,
        manifestLoadingRetryDelay: 500,
        levelLoadingMaxRetry: 6,
        levelLoadingRetryDelay: 500,
      });

      hlsRef.current = hls;

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        setLoading(false);
        video.play().catch((err) => {
          console.error('Autoplay failed:', err);
          setError('Click to play');
        });
      });

      hls.on(Hls.Events.ERROR, (_event, data) => {
        console.error('HLS Error:', data);
        if (data.fatal) {
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              setError('Network error - stream not available');
              hls.startLoad();
              break;
            case Hls.ErrorTypes.MEDIA_ERROR:
              setError('Media error - trying to recover');
              hls.recoverMediaError();
              break;
            default:
              setError('Fatal error - cannot play stream');
              break;
          }
        }
      });

      hls.loadSource(streamUrl);
      hls.attachMedia(video);
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Native HLS support (Safari)
      video.src = streamUrl;
      video.addEventListener('loadedmetadata', () => {
        setLoading(false);
        video.play();
      });
    } else {
      setError('HLS not supported in this browser');
    }

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, [streamUrl]);

  // Fullscreen handlers
  const enterFullscreen = () => {
    setIsFullscreen(true);
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const exitFullscreen = () => {
    setIsFullscreen(false);
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // Zoom handlers
  const handleZoomIn = () => {
    setZoom((prev) => Math.min(prev + 0.5, 5));
  };

  const handleZoomOut = () => {
    setZoom((prev) => {
      const newZoom = Math.max(prev - 0.5, 1);
      if (newZoom === 1) {
        setPan({ x: 0, y: 0 });
      }
      return newZoom;
    });
  };

  const handleResetZoom = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // Pan handlers
  const panStep = 50;
  const handlePan = (direction: 'up' | 'down' | 'left' | 'right') => {
    setPan((prev) => {
      const maxPan = (zoom - 1) * 200;
      let newX = prev.x;
      let newY = prev.y;

      switch (direction) {
        case 'up':
          newY = Math.min(prev.y + panStep, maxPan);
          break;
        case 'down':
          newY = Math.max(prev.y - panStep, -maxPan);
          break;
        case 'left':
          newX = Math.min(prev.x + panStep, maxPan);
          break;
        case 'right':
          newX = Math.max(prev.x - panStep, -maxPan);
          break;
      }

      return { x: newX, y: newY };
    });
  };

  // Reattach HLS when switching between normal and fullscreen views
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !hlsRef.current) return;

    // Ensure HLS is attached to the current video element
    if (hlsRef.current.media !== video) {
      try {
        hlsRef.current.detachMedia();
        hlsRef.current.attachMedia(video);
        video.play().catch((err) => {
          console.error('Playback failed after reattach:', err);
        });
      } catch (err) {
        console.error('Failed to reattach HLS:', err);
      }
    }
  }, [isFullscreen]);

  // Keyboard shortcuts
  useEffect(() => {
    if (!isFullscreen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'Escape':
          exitFullscreen();
          break;
        case '+':
        case '=':
          handleZoomIn();
          break;
        case '-':
        case '_':
          handleZoomOut();
          break;
        case '0':
          handleResetZoom();
          break;
        case 'ArrowUp':
          e.preventDefault();
          handlePan('up');
          break;
        case 'ArrowDown':
          e.preventDefault();
          handlePan('down');
          break;
        case 'ArrowLeft':
          e.preventDefault();
          handlePan('left');
          break;
        case 'ArrowRight':
          e.preventDefault();
          handlePan('right');
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen, zoom]);

  return (
    <>
      {/* Normal view */}
      <div className={`bg-gray-900 rounded-lg overflow-hidden ${isFullscreen ? 'hidden' : ''}`}>
        <div className="bg-gray-800 px-4 py-2 flex items-center justify-between">
          <div className="flex items-center">
            <Video className="w-4 h-4 text-green-500 mr-2" />
            <span className="text-white font-medium">{title}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400">1920x1080 @ 1fps</span>
            <button
              onClick={enterFullscreen}
              className="text-gray-400 hover:text-white transition-colors"
              title="Open fullscreen with zoom controls"
            >
              <Maximize2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div
          className="relative aspect-video bg-black cursor-pointer"
          onClick={enterFullscreen}
          title="Click for fullscreen with zoom controls"
        >
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-white text-sm">Loading stream...</div>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-75">
              <div className="text-center">
                <AlertCircle className="w-12 h-12 text-yellow-500 mx-auto mb-2" />
                <p className="text-white text-sm">{error}</p>
              </div>
            </div>
          )}

          <video
            ref={videoRef}
            className="w-full h-full object-contain"
            muted
            playsInline
            controls={false}
          />
        </div>
      </div>

      {/* Fullscreen view */}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 bg-black flex flex-col">
      {/* Header */}
      <div className="bg-gray-900 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Video className="w-5 h-5 text-green-500" />
          <span className="text-white font-semibold text-lg">{title}</span>
          <span className="text-gray-400 text-sm">1920x1080 @ 1fps</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-white text-sm">Zoom: {zoom.toFixed(1)}x</span>
          <button
            onClick={exitFullscreen}
            className="text-gray-400 hover:text-white transition-colors p-2 hover:bg-gray-800 rounded"
            title="Exit fullscreen (ESC)"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
      </div>

      {/* Video container */}
      <div className="flex-1 relative overflow-hidden">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <div className="text-white text-lg">Loading stream...</div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-75 z-10">
            <div className="text-center">
              <AlertCircle className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
              <p className="text-white text-lg">{error}</p>
            </div>
          </div>
        )}

        <div className="absolute inset-0 flex items-center justify-center">
          {/* Display the video in fullscreen with zoom/pan */}
          <div
            className="max-w-full max-h-full flex items-center justify-center"
            style={{
              transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
              transition: 'transform 0.2s ease-out',
            }}
          >
            <video
              ref={videoRef}
              className="max-w-full max-h-full object-contain"
              muted
              playsInline
              controls={false}
            />
          </div>
        </div>
      </div>

      {/* Control panel */}
      <div className="bg-gray-900 px-6 py-4 border-t border-gray-800">
        <div className="flex items-center justify-center gap-8">
          {/* Zoom controls */}
          <div className="flex items-center gap-2">
            <span className="text-gray-400 text-sm mr-2">Zoom:</span>
            <button
              onClick={handleZoomOut}
              disabled={zoom === 1}
              className="p-2 bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 disabled:text-gray-600 text-white rounded transition-colors"
              title="Zoom out (-)"
            >
              <ZoomOut className="w-5 h-5" />
            </button>
            <button
              onClick={handleResetZoom}
              disabled={zoom === 1}
              className="px-3 py-2 bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 disabled:text-gray-600 text-white rounded transition-colors text-sm"
              title="Reset zoom (0)"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
            <button
              onClick={handleZoomIn}
              disabled={zoom === 5}
              className="p-2 bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 disabled:text-gray-600 text-white rounded transition-colors"
              title="Zoom in (+)"
            >
              <ZoomIn className="w-5 h-5" />
            </button>
          </div>

          {/* Pan controls */}
          {zoom > 1 && (
            <div className="flex items-center gap-2">
              <span className="text-gray-400 text-sm mr-2">Pan:</span>
              <div className="grid grid-cols-3 gap-1">
                <div></div>
                <button
                  onClick={() => handlePan('up')}
                  className="p-2 bg-gray-800 hover:bg-gray-700 text-white rounded transition-colors"
                  title="Pan up (↑)"
                >
                  <ChevronUp className="w-5 h-5" />
                </button>
                <div></div>
                <button
                  onClick={() => handlePan('left')}
                  className="p-2 bg-gray-800 hover:bg-gray-700 text-white rounded transition-colors"
                  title="Pan left (←)"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <div></div>
                <button
                  onClick={() => handlePan('right')}
                  className="p-2 bg-gray-800 hover:bg-gray-700 text-white rounded transition-colors"
                  title="Pan right (→)"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
                <div></div>
                <button
                  onClick={() => handlePan('down')}
                  className="p-2 bg-gray-800 hover:bg-gray-700 text-white rounded transition-colors"
                  title="Pan down (↓)"
                >
                  <ChevronDown className="w-5 h-5" />
                </button>
                <div></div>
              </div>
            </div>
          )}

          {/* Keyboard hints */}
          <div className="text-gray-400 text-xs ml-8">
            <div>ESC: Exit • +/-: Zoom • 0: Reset</div>
            {zoom > 1 && <div>Arrow keys: Pan</div>}
          </div>
        </div>
      </div>
    </div>
      )}
    </>
  );
};
