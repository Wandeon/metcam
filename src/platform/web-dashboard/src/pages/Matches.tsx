import React, { useEffect, useState } from 'react';
import { Download, Film, RefreshCw, Trash2 } from 'lucide-react';

interface RecordingEntry {
  file: string;
  size_mb: number;
  created_at?: number;
}

interface Match {
  id: string;
  files: RecordingEntry[];
  date: string;
  total_size_mb: number;
}

const formatLabel = (file: string) => {
  if (file.includes('cam0')) return 'Camera 0';
  if (file.includes('cam1')) return 'Camera 1';
  return file;
};

export const Matches: React.FC = () => {
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloadModalMatchId, setDownloadModalMatchId] = useState<string | null>(null);
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
            size_mb: f.size_mb || 0,
            created_at: f.created_at,
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
    const interval = setInterval(loadMatches, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleDownloadClick = (matchId: string) => {
    setDownloadModalMatchId(matchId);
  };

  const handleDownloadModalClose = () => {
    setDownloadModalMatchId(null);
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

      {downloadModalMatchId && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          onClick={handleDownloadModalClose}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-md w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-xl font-bold mb-4">Download Recording</h3>
            <p className="text-gray-600 mb-4">
              <strong>{downloadModalMatchId}</strong>
            </p>
            <div className="flex flex-col gap-2">
              {matches.find(m => m.id === downloadModalMatchId)?.files.map((entry) => (
                <a
                  key={entry.file}
                  href={`/recordings/${entry.file}`}
                  download
                  className="flex items-center justify-between px-4 py-3 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm touch-manipulation"
                >
                  <span className="flex items-center">
                    <Download className="w-4 h-4 mr-2" />
                    {formatLabel(entry.file)}
                  </span>
                  <span className="text-xs opacity-75">{entry.size_mb.toFixed(1)} MB</span>
                </a>
              ))}
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
                  {match.files.length} files • {match.total_size_mb.toFixed(1)} MB total
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
