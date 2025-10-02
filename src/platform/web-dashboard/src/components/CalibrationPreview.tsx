import React, { useState, useRef, useEffect } from 'react';
import { ZoomIn, ZoomOut, Move, RotateCcw, Camera, Maximize, Play, Square } from 'lucide-react';

interface CalibrationPreviewProps {
  serverIp: string;
}

export const CalibrationPreview: React.FC<CalibrationPreviewProps> = ({ serverIp }) => {
  const [camera, setCamera] = useState<0 | 1>(0);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [fps] = useState(1);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [isLive, setIsLive] = useState(false);
  const [frameCount, setFrameCount] = useState(0);
  const [imageUrl, setImageUrl] = useState('');
  const [error, setError] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [serviceRunning, setServiceRunning] = useState(false);
  const [checkingStatus, setCheckingStatus] = useState(true);
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const snapshotUrl = `http://${serverIp}/api/v1/preview/calibration/cam${camera}/snapshot`;

  // Check service status on mount
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const response = await fetch(`http://${serverIp}/api/v1/preview/calibration/status`);
        const data = await response.json();
        setServiceRunning(data.running || false);
      } catch (err) {
        console.error('Failed to check calibration status:', err);
      } finally {
        setCheckingStatus(false);
      }
    };
    checkStatus();
  }, [serverIp]);

  const startCalibration = async () => {
    try {
      const response = await fetch(`http://${serverIp}/api/v1/preview/calibration/start`, {
        method: 'POST'
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to start calibration');
      }
      setServiceRunning(true);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start calibration');
    }
  };

  const stopCalibration = async () => {
    try {
      const response = await fetch(`http://${serverIp}/api/v1/preview/calibration/stop`, {
        method: 'POST'
      });
      if (!response.ok) {
        throw new Error('Failed to stop calibration');
      }
      setServiceRunning(false);
      setIsLive(false);
      setImageUrl('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop calibration');
    }
  };

  const handleZoomIn = () => setZoom(Math.min(zoom + 1, 10));
  const handleZoomOut = () => setZoom(Math.max(zoom - 1, 1));
  const handleReset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleMouseDown = (e: React.MouseEvent | React.TouchEvent) => {
    if (zoom > 1) {
      setIsDragging(true);
      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
      const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
      setDragStart({ x: clientX - pan.x, y: clientY - pan.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent | React.TouchEvent) => {
    if (isDragging && zoom > 1) {
      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
      const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
      const maxPan = ((zoom - 1) * 300) / zoom;
      const newX = Math.max(-maxPan, Math.min(maxPan, clientX - dragStart.x));
      const newY = Math.max(-maxPan, Math.min(maxPan, clientY - dragStart.y));
      setPan({ x: newX, y: newY });
    }
  };

  const handleMouseUp = () => setIsDragging(false);

  const toggleFullscreen = async () => {
    if (!containerRef.current) return;

    try {
      if (!document.fullscreenElement) {
        await containerRef.current.requestFullscreen();
        setIsFullscreen(true);
      } else {
        await document.exitFullscreen();
        setIsFullscreen(false);
      }
    } catch (err) {
      console.error('Fullscreen error:', err);
    }
  };

  // Listen for fullscreen changes
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.key === '+' || e.key === '=') handleZoomIn();
      if (e.key === '-' || e.key === '_') handleZoomOut();
      if (e.key === 'r' || e.key === 'R') handleReset();
      if (e.key === 'c' || e.key === 'C') setCamera(c => c === 0 ? 1 : 0);
      if (e.key === 'f' || e.key === 'F') toggleFullscreen();
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [zoom]);

  // Poll for new snapshots every second (only if service is running)
  useEffect(() => {
    if (!serviceRunning) {
      setIsLive(false);
      setFrameCount(0);
      return;
    }

    setFrameCount(0);
    setIsLive(false);
    setError('');

    const fetchSnapshot = async () => {
      try {
        // Add timestamp to prevent caching
        const url = `${snapshotUrl}?t=${Date.now()}`;
        const response = await fetch(url);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const blob = await response.blob();
        const objectUrl = URL.createObjectURL(blob);

        setImageUrl(objectUrl);
        setIsLive(true);
        setError('');
        setFrameCount(prev => prev + 1);

        // Clean up previous object URL
        return objectUrl;
      } catch (err) {
        setIsLive(false);
        setError(err instanceof Error ? err.message : 'Failed to fetch snapshot');
        return null;
      }
    };

    // Fetch first frame immediately
    let currentObjectUrl: string | null = null;
    fetchSnapshot().then(url => { currentObjectUrl = url; });

    // Then poll every 1000ms
    const interval = setInterval(async () => {
      // Revoke previous object URL to prevent memory leak
      if (currentObjectUrl) {
        URL.revokeObjectURL(currentObjectUrl);
      }
      currentObjectUrl = await fetchSnapshot();
    }, 1000);

    return () => {
      clearInterval(interval);
      if (currentObjectUrl) {
        URL.revokeObjectURL(currentObjectUrl);
      }
    };
  }, [snapshotUrl, serviceRunning]);

  return (
    <div className="flex flex-col h-screen bg-gray-900">
      {/* Control Bar */}
      <div className="bg-gray-800 p-2 sm:p-4 border-b border-gray-700">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-4">
          {/* Top row on mobile: Title + Start/Stop + Camera selector */}
          <div className="flex items-center justify-between sm:justify-start gap-2 sm:gap-4">
            <h2 className="text-white text-lg sm:text-xl font-bold">Focus Calibration</h2>

            {/* Start/Stop Button */}
            {!checkingStatus && (
              <button
                onClick={serviceRunning ? stopCalibration : startCalibration}
                className={`px-3 py-2 rounded flex items-center gap-2 text-sm sm:text-base transition-colors ${
                  serviceRunning
                    ? 'bg-red-600 hover:bg-red-700 text-white'
                    : 'bg-green-600 hover:bg-green-700 text-white'
                }`}
              >
                {serviceRunning ? (
                  <>
                    <Square className="w-4 h-4" />
                    <span className="hidden sm:inline">Stop</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    <span className="hidden sm:inline">Start</span>
                  </>
                )}
              </button>
            )}

            {/* Camera Selector */}
            <div className="flex gap-1 sm:gap-2">
              <button
                onClick={() => setCamera(0)}
                className={`px-2 py-1 sm:px-4 sm:py-2 rounded flex items-center gap-1 sm:gap-2 text-xs sm:text-base transition-colors ${
                  camera === 0 ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                <Camera className="w-3 h-3 sm:w-4 sm:h-4" />
                <span className="hidden sm:inline">Camera 0</span>
                <span className="sm:hidden">C0</span>
              </button>
              <button
                onClick={() => setCamera(1)}
                className={`px-2 py-1 sm:px-4 sm:py-2 rounded flex items-center gap-1 sm:gap-2 text-xs sm:text-base transition-colors ${
                  camera === 1 ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                <Camera className="w-3 h-3 sm:w-4 sm:h-4" />
                <span className="hidden sm:inline">Camera 1</span>
                <span className="sm:hidden">C1</span>
              </button>
            </div>
          </div>

          {/* Bottom row on mobile: Zoom controls + Fullscreen */}
          <div className="flex items-center justify-between sm:justify-end gap-2 sm:gap-4">
            {/* Zoom Controls - Larger touch targets */}
            <div className="flex items-center gap-1 sm:gap-2">
              <button
                onClick={handleZoomOut}
                disabled={zoom <= 1}
                className="p-3 bg-gray-700 text-white rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors touch-manipulation"
                title="Zoom out (-)"
              >
                <ZoomOut className="w-5 h-5" />
              </button>

              <div className="text-white font-mono bg-gray-700 px-3 sm:px-4 py-2 rounded text-sm sm:text-base min-w-[60px] sm:min-w-[80px] text-center">
                {zoom.toFixed(1)}x
              </div>

              <button
                onClick={handleZoomIn}
                disabled={zoom >= 10}
                className="p-3 bg-gray-700 text-white rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors touch-manipulation"
                title="Zoom in (+)"
              >
                <ZoomIn className="w-5 h-5" />
              </button>

              <button
                onClick={handleReset}
                className="p-3 bg-gray-700 text-white rounded hover:bg-gray-600 transition-colors touch-manipulation"
                title="Reset view (R)"
              >
                <RotateCcw className="w-5 h-5" />
              </button>
            </div>

            {/* Fullscreen Button */}
            <button
              onClick={toggleFullscreen}
              className="p-3 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors touch-manipulation"
              title="Fullscreen (F)"
            >
              <Maximize className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Preview Area */}
      <div
        ref={containerRef}
        className={`flex-1 relative overflow-hidden bg-black touch-none ${
          zoom > 1 ? 'cursor-move' : 'cursor-pointer'
        }`}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onTouchStart={handleMouseDown}
        onTouchMove={handleMouseMove}
        onTouchEnd={handleMouseUp}
        onClick={(e) => {
          // Click to fullscreen when not zoomed and not dragging
          if (zoom === 1 && !isDragging && e.target === containerRef.current) {
            toggleFullscreen();
          }
        }}
      >
        {imageUrl && (
          <img
            ref={imgRef}
            src={imageUrl}
            alt={`Camera ${camera} Preview`}
            className="absolute inset-0 w-full h-full object-contain select-none"
            style={{
              transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
              cursor: zoom > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default',
              imageRendering: zoom > 3 ? 'pixelated' : 'auto',
              transition: isDragging ? 'none' : 'transform 0.2s ease-out'
            }}
            draggable={false}
          />
        )}

        {/* Zoom Indicator */}
        {zoom > 1 && (
          <div className="absolute top-2 left-2 sm:top-4 sm:left-4 bg-black bg-opacity-75 text-white px-2 py-1 sm:px-4 sm:py-2 rounded flex items-center gap-1 sm:gap-2 text-xs sm:text-base">
            <Move className="w-3 h-3 sm:w-4 sm:h-4" />
            <span className="hidden sm:inline">Drag to pan</span>
            <span className="sm:hidden">Pan</span>
          </div>
        )}

        {/* Fullscreen Hint */}
        {!isFullscreen && zoom === 1 && isLive && (
          <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 bg-black bg-opacity-75 text-white px-3 py-1 rounded text-xs sm:text-sm pointer-events-none">
            Click or press F for fullscreen
          </div>
        )}

        {/* Center Crosshair (for focus reference) */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2">
            {/* Horizontal line */}
            <div className="absolute w-16 h-0.5 bg-green-500 opacity-50 left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2"></div>
            {/* Vertical line */}
            <div className="absolute w-0.5 h-16 bg-green-500 opacity-50 left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2"></div>
            {/* Center dot */}
            <div className="absolute w-2 h-2 bg-green-500 rounded-full left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2"></div>
          </div>
        </div>

        {/* Connection Status */}
        {!isLive && (
          <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50">
            <div className="bg-gray-800 text-white px-6 py-4 rounded-lg max-w-md">
              <div className="animate-pulse">Connecting to camera {camera}...</div>
              <div className="text-sm text-gray-400 mt-2">Endpoint: {snapshotUrl}</div>
              {error && (
                <div className="text-sm text-red-400 mt-2">
                  Error: {error}
                </div>
              )}
              <div className="text-xs text-gray-500 mt-3">
                Make sure calibration preview service is running
              </div>
            </div>
          </div>
        )}

        {/* Frame Counter (top right) */}
        {isLive && frameCount > 0 && (
          <div className="absolute top-2 right-2 sm:top-4 sm:right-4 bg-black bg-opacity-75 text-green-400 px-2 py-1 sm:px-3 rounded text-xs sm:text-sm font-mono">
            <span className="hidden sm:inline">Frame {frameCount}</span>
            <span className="sm:hidden">#{frameCount}</span>
          </div>
        )}
      </div>

      {/* Status Bar */}
      {!isFullscreen && (
        <div className="bg-gray-800 p-2 sm:p-3 border-t border-gray-700">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs sm:text-sm">
            <div className="text-gray-400 font-mono">
              <span className="hidden sm:inline">Camera {camera} • Full resolution @ {fps}fps • Snapshot mode</span>
              <span className="sm:hidden">C{camera} • {fps}fps</span>
            </div>
            <div className="text-gray-400 font-mono hidden sm:block">
              Pan: ({pan.x.toFixed(0)}, {pan.y.toFixed(0)}) • Zoom: {zoom}x • Frame: {frameCount}
            </div>
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${isLive ? 'bg-green-500' : 'bg-yellow-500'} animate-pulse`}></div>
              <span className={isLive ? 'text-green-400' : 'text-yellow-400'}>
                {isLive ? 'Live' : 'Connecting'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
