import React, { useEffect, useRef, useState } from 'react';
import Hls from 'hls.js';
import { Video, AlertCircle } from 'lucide-react';

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
        lowLatencyMode: false,
        backBufferLength: 90,
        maxBufferLength: 30,
        maxMaxBufferLength: 60,
        maxBufferSize: 60 * 1000 * 1000,
        maxBufferHole: 0.5,
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

  return (
    <div className="bg-gray-900 rounded-lg overflow-hidden">
      <div className="bg-gray-800 px-4 py-2 flex items-center justify-between">
        <div className="flex items-center">
          <Video className="w-4 h-4 text-green-500 mr-2" />
          <span className="text-white font-medium">{title}</span>
        </div>
        <span className="text-xs text-gray-400">4032x3040 @ 5fps</span>
      </div>

      <div className="relative aspect-[4/3] bg-black">
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
  );
};
