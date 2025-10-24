import React, { useEffect, useState } from 'react';
import { Download, Film, RefreshCw, Trash2, ChevronRight, ArrowLeft, Package } from 'lucide-react';

interface RecordingEntry {
  file: string;
  filename?: string;
  size_mb: number;
  created_at?: number;
  segment_count?: number;
  type?: 'segmented' | 'single';
}

interface Match {
  id: string;
  files: RecordingEntry[];
  date: string;
  total_size_mb: number;
}

interface SegmentInfo {
  name: string;
  path: string;
  size_mb: number;
  created_at: number;
  segment_number: number;
}

interface SegmentDetails {
  match_id: string;
  type: 'segmented' | 'merged';
  cam0: SegmentInfo[];
  cam1: SegmentInfo[];
  total_size_mb: number;
  segment_duration_minutes?: number;
}

const formatLabel = (file: string) => {
  if (file.includes('cam0')) return 'Camera 0';
  if (file.includes('cam1')) return 'Camera 1';
  return file;
};

const formatSize = (mb: number) => {
  if (mb >= 1000) {
    return `${(mb / 1024).toFixed(2)} GB`;
  }
  return `${mb.toFixed(1)} MB`;
};

const formatTimestamp = (timestamp: number) => {
  const date = new Date(timestamp * 1000);
  return date.toLocaleTimeString();
};

export const Matches: React.FC = () => {
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloadModalMatchId, setDownloadModalMatchId] = useState<string | null>(null);
  const [segmentModal, setSegmentModal] = useState<{ matchId: string; camera: 'cam0' | 'cam1' } | null>(null);
  const [segmentDetails, setSegmentDetails] = useState<SegmentDetails | null>(null);
  const [loadingSegments, setLoadingSegments] = useState(false);
  const [deletingMatchId, setDeletingMatchId] = useState<string | null>(null);

  const loadMatches = async () => {
    try {
      const response = await fetch('/api/v1/recordings');
      const data = await response.json();

      if (!data.recordings) {
        setMatches([]);
        return;
      }

      const matchList: Match[] = Object.entries(data.recordings).map(
        ([matchId, files]) => {
          const entries: RecordingEntry[] = (files as any[]).map((f: any) => ({
            file: f.file || f.filename || f,
            filename: f.filename,
            size_mb: f.size_mb || 0,
            created_at: f.created_at,
            segment_count: f.segment_count,
            type: f.type || (f.segment_count && f.segment_count > 1 ? 'segmented' : 'single'),
          }));

          const totalSize = entries.reduce((sum, entry) => sum + entry.size_mb, 0);
          const firstTimestamp = entries[0]?.created_at
            ? new Date(entries[0].created_at * 1000).toISOString()
            : new Date().toISOString();

          return {
            id: matchId,
            files: entries,
            date: firstTimestamp,
            total_size_mb: totalSize,
          };
        }
      );

      setMatches(matchList.sort((a, b) => (a.date > b.date ? -1 : 1)));
    } catch (error) {
      console.error('Failed to load matches:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMatches();
    const interval = setInterval(loadMatches, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleDownloadClick = (matchId: string) => {
    setDownloadModalMatchId(matchId);
  };

  const handleDownloadModalClose = () => {
    setDownloadModalMatchId(null);
    setSegmentModal(null);
    setSegmentDetails(null);
  };

  const handleCameraClick = async (matchId: string, camera: 'cam0' | 'cam1') => {
    setSegmentModal({ matchId, camera });
    setLoadingSegments(true);

    try {
      const response = await fetch(`/api/v1/recordings/${matchId}/segments`);
      const data = await response.json();
      setSegmentDetails(data);
    } catch (error) {
      console.error('Failed to load segments:', error);
      alert('Failed to load segment details');
      setSegmentModal(null);
    } finally {
      setLoadingSegments(false);
    }
  };

  const handleBackToCamera = () => {
    setSegmentModal(null);
    setSegmentDetails(null);
  };

  const handleDeleteClick = async (matchId: string) => {
    if (!confirm(`Are you sure you want to delete recording "${matchId}"?`)) {
      return;
    }

    setDeletingMatchId(matchId);
    try {
      const response = await fetch(`/api/v1/recordings/${matchId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        setMatches(prev => prev.filter(m => m.id !== matchId));
      } else {
        alert('Failed to delete recording');
      }
    } catch (error) {
      console.error('Failed to delete recording:', error);
      alert('Failed to delete recording');
    } finally {
      setDeletingMatchId(null);
    }
  };

  if (loading) {
    return (
      <div className="p-4 md:p-6 animate-pulse">Loading recordings…</div>
    );
  }

  const currentMatch = downloadModalMatchId ? matches.find(m => m.id === downloadModalMatchId) : null;
  const currentSegments = segmentModal && segmentDetails
    ? segmentDetails[segmentModal.camera]
    : [];

  return (
    <div className="p-4 md:p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Matches</h1>
        <button
          onClick={loadMatches}
          className="flex items-center px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 touch-manipulation"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </button>
      </div>

      {/* Level 1: Camera Selection Modal */}
      {downloadModalMatchId && !segmentModal && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          onClick={handleDownloadModalClose}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-md w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-xl font-bold mb-2">Download Recording</h3>
            <p className="text-gray-600 mb-4">
              <strong>{downloadModalMatchId}</strong>
            </p>

            <div className="flex flex-col gap-2">
              {currentMatch?.files.map((entry) => {
                const isSegmented = entry.type === 'segmented' || (entry.segment_count && entry.segment_count > 1);
                const camera = entry.file.includes('cam0') ? 'cam0' : 'cam1';

                return (
                  <button
                    key={entry.file}
                    onClick={() => isSegmented
                      ? handleCameraClick(downloadModalMatchId, camera)
                      : window.location.href = `/recordings/${downloadModalMatchId}/segments/${entry.file}`
                    }
                    className="flex items-center justify-between px-4 py-3 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm touch-manipulation"
                  >
                    <span className="flex items-center">
                      <Download className="w-4 h-4 mr-2" />
                      {formatLabel(entry.file)}
                      {isSegmented && entry.segment_count && (
                        <span className="ml-2 px-2 py-0.5 bg-blue-500 rounded text-xs">
                          {entry.segment_count} segments
                        </span>
                      )}
                    </span>
                    <span className="flex items-center gap-2">
                      <span className="text-xs opacity-75">{formatSize(entry.size_mb)}</span>
                      {isSegmented && <ChevronRight className="w-4 h-4" />}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="flex justify-end mt-6">
              <button
                onClick={handleDownloadModalClose}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Level 2: Segment Details Modal */}
      {segmentModal && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          onClick={handleDownloadModalClose}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center mb-4">
              <button
                onClick={handleBackToCamera}
                className="mr-3 p-1 hover:bg-gray-100 rounded"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h3 className="text-xl font-bold">
                  {segmentModal.camera === 'cam0' ? 'Camera 0' : 'Camera 1'} - Segments
                </h3>
                <p className="text-sm text-gray-600">{segmentModal.matchId}</p>
              </div>
            </div>

            {loadingSegments ? (
              <div className="py-8 text-center text-gray-500">
                Loading segments...
              </div>
            ) : (
              <>
                {/* Summary Box */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <span className="text-sm font-medium text-gray-700">Total Segments:</span>
                      <span className="ml-2 text-lg font-bold text-blue-600">
                        {currentSegments.length}
                      </span>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-gray-700">Total Size:</span>
                      <span className="ml-2 text-lg font-bold text-blue-600">
                        {formatSize(currentSegments.reduce((sum, s) => sum + s.size_mb, 0))}
                      </span>
                    </div>
                    {segmentDetails?.segment_duration_minutes && (
                      <div className="col-span-2">
                        <span className="text-sm font-medium text-gray-700">Segment Duration:</span>
                        <span className="ml-2 text-sm text-gray-600">
                          ~{segmentDetails.segment_duration_minutes} minutes each
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Download All Button */}
                <div className="mb-4">
                  <button
                    onClick={() => {
                      // TODO: Implement download all as zip
                      alert('Download all segments functionality coming soon');
                    }}
                    className="w-full flex items-center justify-center px-4 py-3 bg-green-600 text-white rounded hover:bg-green-700 font-medium touch-manipulation"
                  >
                    <Package className="w-5 h-5 mr-2" />
                    Download All Segments ({currentSegments.length} files)
                  </button>
                </div>

                {/* Segment List */}
                <div className="space-y-2">
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Individual Segments:</h4>
                  {currentSegments.map((segment) => (
                    <div
                      key={segment.name}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded border border-gray-200 hover:bg-gray-100"
                    >
                      <div className="flex-1">
                        <div className="font-medium text-sm">
                          Segment {segment.segment_number + 1}
                        </div>
                        <div className="text-xs text-gray-500">
                          {formatSize(segment.size_mb)} • {formatTimestamp(segment.created_at)}
                        </div>
                      </div>
                      <a
                        href={segment.path}
                        download
                        className="flex items-center px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm touch-manipulation ml-2"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Download className="w-4 h-4 mr-1" />
                        Download
                      </a>
                    </div>
                  ))}
                </div>
              </>
            )}

            <div className="flex justify-between mt-6">
              <button
                onClick={handleBackToCamera}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              >
                Back to Cameras
              </button>
              <button
                onClick={handleDownloadModalClose}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-4">
        {matches.map((match) => (
          <div key={match.id} className="bg-white rounded-lg shadow p-4 md:p-6">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold">{match.id}</h3>
                <p className="text-gray-600 text-sm">
                  {new Date(match.date).toLocaleDateString()} at {new Date(match.date).toLocaleTimeString()}
                </p>
                <p className="text-gray-500 text-xs mt-1">
                  {match.files.length} {match.files.length === 1 ? 'camera' : 'cameras'} • {formatSize(match.total_size_mb)} total
                  {match.files.some(f => f.type === 'segmented' || (f.segment_count && f.segment_count > 1)) &&
                    <span className="ml-1">• Segmented Recording</span>
                  }
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => handleDownloadClick(match.id)}
                  className="flex items-center px-3 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm touch-manipulation"
                >
                  <Download className="w-4 h-4 mr-1" />
                  Download
                </button>

                <button
                  onClick={() => handleDeleteClick(match.id)}
                  disabled={deletingMatchId === match.id}
                  className={`flex items-center px-3 py-2 rounded text-sm touch-manipulation ${
                    deletingMatchId === match.id
                      ? 'bg-gray-400 text-gray-200 cursor-not-allowed'
                      : 'bg-red-600 text-white hover:bg-red-700'
                  }`}
                >
                  <Trash2 className="w-4 h-4 mr-1" />
                  {deletingMatchId === match.id ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        ))}

        {matches.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <Film className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <p>No recordings yet</p>
          </div>
        )}
      </div>
    </div>
  );
};

export { Matches as MatchesEnhanced };
