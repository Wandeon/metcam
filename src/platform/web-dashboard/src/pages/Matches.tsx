import React, { useState, useEffect } from 'react';
import { Film, Download, Video, Upload, RefreshCw } from 'lucide-react';

interface Match {
  id: string;
  files: string[];
  sidebyside_exists?: boolean;
  date: string;
  total_size_mb: number;
  upload_status?: 'uploading' | 'completed' | 'failed' | 'pending';
  upload_progress?: number;
}

export const Matches: React.FC = () => {
  const [matches, setMatches] = useState<Match[]>([]);
  const [processing, setProcessing] = useState<{ [key: string]: any }>({});
  const [uploading, setUploading] = useState<{ [key: string]: any }>({});

  useEffect(() => {
    loadMatches();

    // Poll for processing/upload status
    const interval = setInterval(() => {
      updateJobStatuses();
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const loadMatches = async () => {
    try {
      // Get list of recording files
      const response = await fetch('/api/v1/recordings');
      const data = await response.json();

      // Get upload status from activity log
      const activityResponse = await fetch('/api/v1/activity/?limit=200');
      const activityData = await activityResponse.json();

      // Group by match ID
      const matchMap: { [key: string]: Match } = {};

      if (data.recordings) {
        Object.keys(data.recordings).forEach((matchId) => {
          const files = data.recordings[matchId];
          const totalSize = files.reduce((sum: number, f: any) => sum + (f.size_mb || 0), 0);

          // Check upload status from activity log
          const uploadEvents = activityData.events?.filter((e: any) =>
            e.match_id === matchId || e.details?.match_id === matchId
          ) || [];

          let upload_status: Match['upload_status'] = 'pending';
          if (uploadEvents.some((e: any) => e.event_type === 'upload_completed')) {
            upload_status = 'completed';
          } else if (uploadEvents.some((e: any) => e.event_type === 'upload_started')) {
            upload_status = 'uploading';
          } else if (uploadEvents.some((e: any) => e.severity === 'error')) {
            upload_status = 'failed';
          }

          matchMap[matchId] = {
            id: matchId,
            files: files.map((f: any) => f.file || f.filename || f),
            sidebyside_exists: files.some((f: any) =>
              (f.file || f.filename || f).includes('_sidebyside.mp4')
            ),
            date: files[0]?.created_at ? new Date(files[0].created_at * 1000).toISOString() : new Date().toISOString(),
            total_size_mb: totalSize,
            upload_status
          };
        });
      }

      setMatches(Object.values(matchMap));
    } catch (error) {
      console.error('Failed to load matches:', error);
    }
  };

  const updateJobStatuses = async () => {
    // Update processing jobs
    for (const jobId of Object.keys(processing)) {
      try {
        const response = await fetch(`/api/v1/processing/status/${jobId}`);
        const status = await response.json();
        setProcessing(prev => ({ ...prev, [jobId]: status }));

        if (status.status === 'completed' || status.status === 'failed') {
          // Reload matches to show new sidebyside file
          setTimeout(loadMatches, 1000);
        }
      } catch (e) {
        // Job might not exist yet
      }
    }

    // Update upload jobs
    for (const jobId of Object.keys(uploading)) {
      try {
        const response = await fetch(`/api/v1/upload/status/${jobId}`);
        const status = await response.json();
        setUploading(prev => ({ ...prev, [jobId]: status }));
      } catch (e) {
        // Job might not exist yet
      }
    }
  };

  const startProcessing = async (matchId: string) => {
    try {
      const response = await fetch('/api/v1/processing/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ match_id: matchId })
      });

      const data = await response.json();
      setProcessing(prev => ({
        ...prev,
        [data.job_id]: { status: 'starting', progress: 0, match_id: matchId }
      }));
    } catch (error) {
      alert(`Failed to start processing: ${error}`);
    }
  };

  const startUpload = async (matchId: string) => {
    const filePath = `/mnt/recordings/${matchId}_sidebyside.mp4`;

    try {
      const response = await fetch('/api/v1/upload/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: filePath })
      });

      const data = await response.json();
      setUploading(prev => ({
        ...prev,
        [data.job_id]: { status: 'starting', progress: 0, match_id: matchId }
      }));
    } catch (error) {
      alert(`Failed to start upload: ${error}`);
    }
  };

  const getProcessingStatus = (matchId: string) => {
    const job = Object.values(processing).find((j: any) => j.match_id === matchId);
    return job;
  };

  const getUploadStatus = (matchId: string) => {
    const job = Object.values(uploading).find((j: any) => j.match_id === matchId);
    return job;
  };

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

      <div className="grid gap-4">
        {matches.map((match) => {
          const procStatus = getProcessingStatus(match.id);
          const uploadStatus = getUploadStatus(match.id);

          return (
            <div key={match.id} className="bg-white rounded-lg shadow p-4 md:p-6">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold">{match.id}</h3>
                  <p className="text-gray-600 text-sm">
                    {new Date(match.date).toLocaleDateString()} at {new Date(match.date).toLocaleTimeString()}
                  </p>
                  <p className="text-gray-500 text-xs mt-1">
                    {match.files.length} files • {match.total_size_mb.toFixed(1)} MB total
                    {match.sidebyside_exists && ' • Side-by-side ✓'}
                  </p>
                  {match.upload_status && (
                    <div className="flex items-center gap-2 mt-2">
                      {match.upload_status === 'uploading' && (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-100 text-blue-800">
                          <Upload className="w-3 h-3 mr-1 animate-pulse" />
                          Uploading to VPS-02
                        </span>
                      )}
                      {match.upload_status === 'completed' && (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-green-100 text-green-800">
                          ✓ Uploaded to VPS-02
                        </span>
                      )}
                      {match.upload_status === 'failed' && (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-red-100 text-red-800">
                          ✗ Upload failed
                        </span>
                      )}
                      {match.upload_status === 'pending' && (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-gray-100 text-gray-600">
                          Pending upload
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap gap-2">
                  {/* Download Buttons */}
                  {match.files.map(file => (
                    <a
                      key={file}
                      href={`/recordings/${file}`}
                      download
                      className="flex items-center px-3 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm touch-manipulation"
                    >
                      <Download className="w-4 h-4 mr-1" />
                      {file.includes('cam0') ? 'Cam0' : file.includes('cam1') ? 'Cam1' : 'Side-by-side'}
                    </a>
                  ))}

                  {/* Process Button */}
                  {!match.sidebyside_exists && !procStatus && (
                    <button
                      onClick={() => startProcessing(match.id)}
                      className="flex items-center px-3 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 text-sm touch-manipulation"
                    >
                      <Video className="w-4 h-4 mr-1" />
                      Create Side-by-Side
                    </button>
                  )}

                  {/* Processing Status */}
                  {procStatus && procStatus.status !== 'completed' && (
                    <div className="flex items-center px-3 py-2 bg-yellow-100 text-yellow-800 rounded text-sm">
                      <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
                      {procStatus.progress}% - {procStatus.message}
                    </div>
                  )}

                  {/* Upload Button */}
                  {match.sidebyside_exists && !uploadStatus && (
                    <button
                      onClick={() => startUpload(match.id)}
                      className="flex items-center px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm touch-manipulation"
                    >
                      <Upload className="w-4 h-4 mr-1" />
                      Upload to Website
                    </button>
                  )}

                  {/* Upload Status */}
                  {uploadStatus && uploadStatus.status !== 'completed' && (
                    <div className="flex items-center px-3 py-2 bg-green-100 text-green-800 rounded text-sm">
                      <Upload className="w-4 h-4 mr-1 animate-pulse" />
                      {uploadStatus.progress}% - {uploadStatus.message}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}

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
