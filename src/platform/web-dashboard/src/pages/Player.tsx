import React, { useEffect, useState } from 'react';
import { Play, Loader2, RefreshCw, Cloud, X } from 'lucide-react';
import { apiService } from '@/services/api';
import type { R2Match, R2ArchiveFile } from '@/services/api';

const formatSize = (mb: number) => {
  if (mb >= 1000) return `${(mb / 1024).toFixed(2)} GB`;
  return `${mb.toFixed(1)} MB`;
};

const getVideoLabel = (name: string) => {
  if (name.includes('panorama')) return 'Panorama (3840x1080)';
  if (name.includes('cam0')) return 'Camera 0 (1920x1080)';
  if (name.includes('cam1')) return 'Camera 1 (1920x1080)';
  return name;
};

export const Player: React.FC = () => {
  const [matches, setMatches] = useState<R2Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeMatchId, setActiveMatchId] = useState<string | null>(null);
  const [activeVideo, setActiveVideo] = useState<R2ArchiveFile | null>(null);

  const loadArchives = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiService.listR2Archives();
      if (data.success) {
        setMatches(data.matches);
      } else {
        setError('Failed to load cloud archives');
      }
    } catch (err: any) {
      if (err.response?.status === 503) {
        setError('Cloud storage (R2) is not configured on this device.');
      } else {
        setError(err.message || 'Failed to connect to cloud storage');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadArchives();
  }, []);

  const handlePlay = (match: R2Match, file?: R2ArchiveFile) => {
    setActiveMatchId(match.match_id);
    const target = file || match.files.find(f => f.name.includes('panorama')) || match.files[0];
    setActiveVideo(target);
  };

  const handleClose = () => {
    setActiveMatchId(null);
    setActiveVideo(null);
  };

  const activeMatch = activeMatchId ? matches.find(m => m.match_id === activeMatchId) : null;

  if (loading) {
    return (
      <div className="p-4 md:p-6">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500 mr-3" />
          <span className="text-gray-600">Loading cloud recordings...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold">Player</h1>
          <p className="text-sm text-gray-600 mt-1">
            Stream recordings directly from Cloudflare R2
          </p>
        </div>
        <button
          onClick={loadArchives}
          className="flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 touch-manipulation"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-6 py-4 mb-6">
          <p className="text-red-800 font-medium">{error}</p>
        </div>
      )}

      {/* Video Player Modal */}
      {activeMatch && activeVideo && (
        <div
          className="fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center z-50 p-4"
          onClick={handleClose}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[95vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 md:p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-xl font-bold">{activeMatch.match_id}</h3>
                  <p className="text-sm text-gray-500">{getVideoLabel(activeVideo.name)}</p>
                </div>
                <button
                  onClick={handleClose}
                  className="p-1 hover:bg-gray-100 rounded"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="bg-black rounded-lg overflow-hidden mb-4">
                <video
                  key={activeVideo.url}
                  controls
                  autoPlay
                  className="w-full"
                  style={{
                    maxHeight: '65vh',
                    aspectRatio: activeVideo.name.includes('panorama') ? '32/9' : '16/9',
                  }}
                >
                  <source src={activeVideo.url} type="video/mp4" />
                  Your browser does not support video playback.
                </video>
              </div>

              {activeMatch.files.length > 1 && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4">
                  {activeMatch.files.map((file) => {
                    const isActive = file.key === activeVideo.key;
                    return (
                      <button
                        key={file.key}
                        onClick={() => setActiveVideo(file)}
                        className={`px-4 py-3 rounded border text-sm font-medium transition-colors touch-manipulation text-left ${
                          isActive
                            ? 'bg-green-600 text-white border-green-600'
                            : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-100'
                        }`}
                      >
                        <span className="block">{getVideoLabel(file.name)}</span>
                        <span className={`text-xs ${isActive ? 'text-green-100' : 'text-gray-500'}`}>
                          {formatSize(file.size_mb)}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}

              <p className="text-xs text-gray-400 text-center">
                Streaming from Cloudflare R2. URL expires in 1 hour.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Match List */}
      {!error && matches.length === 0 && (
        <div className="text-center py-16 text-gray-500">
          <Cloud className="w-16 h-16 mx-auto mb-4 opacity-40" />
          <p className="font-medium">No cloud recordings</p>
          <p className="text-sm mt-1">Recordings will appear here after post-processing uploads them to R2.</p>
        </div>
      )}

      <div className="grid gap-4">
        {matches.map((match) => {
          const hasPanorama = match.files.some(f => f.name.includes('panorama'));
          const cameraFiles = match.files.filter(f => !f.name.includes('panorama'));

          return (
            <div key={match.match_id} className="bg-white rounded-lg shadow p-4 md:p-6">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold">{match.match_id}</h3>
                  <p className="text-gray-500 text-xs mt-1">
                    {match.files.length} {match.files.length === 1 ? 'file' : 'files'}
                    <span className="ml-1">
                      {formatSize(match.total_size_mb)} total
                    </span>
                    {hasPanorama && (
                      <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                        Panorama
                      </span>
                    )}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  {hasPanorama && (
                    <button
                      onClick={() => handlePlay(match, match.files.find(f => f.name.includes('panorama')))}
                      className="flex items-center px-3 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 text-sm touch-manipulation"
                    >
                      <Play className="w-4 h-4 mr-1" />
                      Panorama
                    </button>
                  )}
                  {cameraFiles.map((file) => (
                    <button
                      key={file.key}
                      onClick={() => handlePlay(match, file)}
                      className="flex items-center px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm touch-manipulation"
                    >
                      <Play className="w-4 h-4 mr-1" />
                      {file.name.includes('cam0') ? 'Cam 0' : file.name.includes('cam1') ? 'Cam 1' : file.name}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
