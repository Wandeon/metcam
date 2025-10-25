import React, { useEffect, useMemo, useState } from 'react';
import { Download, Film, RefreshCw, Trash2, Package } from 'lucide-react';

interface RecordingEntry {
  file: string;
  filename?: string;
  size_mb: number;
  created_at?: number;
  createdAtMs?: number;
  segment_count?: number;
  type?: 'segmented' | 'single';
}

interface Match {
  id: string;
  files: RecordingEntry[];
  date: number;
  total_size_mb: number;
  cameraCount: number;
  segmentsCount: number;
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

const formatTimestamp = (timestamp?: number) => {
  if (!timestamp) {
    return 'Unknown time';
  }

  const normalized = timestamp < 1e12 ? timestamp * 1000 : timestamp;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) {
    return 'Unknown time';
  }
  return date.toLocaleString();
};

const parseTimestampFromString = (value?: string): number | null => {
  if (!value) {
    return null;
  }

  const fullMatch = value.match(/(20\d{2})[-_]?([01]?\d)[-_]?([0-3]?\d)[T\s_-]?([0-2]?\d)[:\-]?([0-5]?\d)[:\-]?([0-5]?\d)/);
  if (fullMatch) {
    const [, yearStr, monthStr, dayStr, hourStr, minuteStr, secondStr] = fullMatch;
    const year = Number(yearStr);
    if (!Number.isFinite(year)) {
      return null;
    }
    const month = Number(monthStr) || 1;
    const day = Number(dayStr) || 1;
    const hour = Number(hourStr) || 0;
    const minute = Number(minuteStr) || 0;
    const second = Number(secondStr) || 0;
    const parsed = new Date(year, month - 1, day, hour, minute, second);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.getTime();
    }
  }

  const dateMatch = value.match(/(20\d{2})[-_]?([01]?\d)[-_]?([0-3]?\d)/);
  if (dateMatch) {
    const [, yearStr, monthStr, dayStr] = dateMatch;
    const year = Number(yearStr);
    if (!Number.isFinite(year)) {
      return null;
    }
    const month = Number(monthStr) || 1;
    const day = Number(dayStr) || 1;
    const parsed = new Date(year, month - 1, day);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.getTime();
    }
  }

  return null;
};

const getCameraKey = (file: string) => {
  if (file.includes('cam0')) return 'cam0';
  if (file.includes('cam1')) return 'cam1';
  return file;
};

export const Matches: React.FC = () => {
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloadModalMatchId, setDownloadModalMatchId] = useState<string | null>(null);
  const [segmentDetails, setSegmentDetails] = useState<SegmentDetails | null>(null);
  const [segmentsLoading, setSegmentsLoading] = useState(false);
  const [activeCamera, setActiveCamera] = useState<'cam0' | 'cam1'>('cam0');
  const [deletingMatchId, setDeletingMatchId] = useState<string | null>(null);
  const [diskStatus, setDiskStatus] = useState<{ freeGb: number; percentUsed: number } | null>(null);
  const [sortOption, setSortOption] = useState<'date_desc' | 'date_asc' | 'name_asc' | 'name_desc' | 'size_desc' | 'size_asc'>('date_desc');
  const [debugInfo, setDebugInfo] = useState<string>('');

  const sortedMatches = useMemo(() => {
    const matchesCopy = [...matches];
    matchesCopy.sort((a, b) => {
      switch (sortOption) {
        case 'date_asc':
          return a.date - b.date;
        case 'name_asc':
          return a.id.localeCompare(b.id);
        case 'name_desc':
          return b.id.localeCompare(a.id);
        case 'size_asc':
          return a.total_size_mb - b.total_size_mb;
        case 'size_desc':
          return b.total_size_mb - a.total_size_mb;
        case 'date_desc':
        default:
          return b.date - a.date;
      }
    });
    return matchesCopy;
  }, [matches, sortOption]);

  const currentMatch = downloadModalMatchId ? matches.find(m => m.id === downloadModalMatchId) : null;

  const cameraSegments = useMemo(() => {
    if (!segmentDetails) {
      return [] as SegmentInfo[];
    }
    const segments = segmentDetails[activeCamera] || [];
    return [...segments].sort((a, b) => a.segment_number - b.segment_number);
  }, [segmentDetails, activeCamera]);

  const cameraFileMap = useMemo(() => {
    const map: Record<'cam0' | 'cam1', RecordingEntry | undefined> = { cam0: undefined, cam1: undefined };
    currentMatch?.files.forEach(entry => {
      const cameraKey = getCameraKey(entry.file);
      if (cameraKey === 'cam0' || cameraKey === 'cam1') {
        map[cameraKey] = entry;
      }
    });
    return map;
  }, [currentMatch]);

  const hasSegmentedFiles = currentMatch?.files.some(
    entry => entry.type === 'segmented' || (entry.segment_count && entry.segment_count > 1)
  );

  const singleFiles = currentMatch?.files.filter(
    entry => !(entry.type === 'segmented' || (entry.segment_count && entry.segment_count > 1))
  ) ?? [];

  const loadMatches = async () => {
    try {
      setDebugInfo('Fetching data...');
      const [recordingsResponse, healthResponse] = await Promise.all([
        fetch('/api/v1/recordings'),
        fetch('/api/v1/health').catch(() => null),
      ]);

      const data = await recordingsResponse.json();
      setDebugInfo(`API response: ${JSON.stringify(data).substring(0, 100)}...`);

      if (healthResponse && healthResponse.ok) {
        try {
          const health = await healthResponse.json();
          if (health?.system) {
            const freeGbRaw = health.system.disk_free_gb;
            const percentUsedRaw = health.system.disk_percent;
            if (typeof freeGbRaw === 'number' && typeof percentUsedRaw === 'number') {
              setDiskStatus({
                freeGb: freeGbRaw,
                percentUsed: percentUsedRaw,
              });
            } else {
              setDiskStatus(null);
            }
          }
        } catch (error) {
          console.warn('Unable to parse disk status', error);
        }
      } else if (healthResponse) {
        setDiskStatus(null);
      }

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
          })).map((entry) => {
            const explicitTimestamp = typeof entry.created_at === 'number'
              ? entry.created_at * 1000
              : typeof entry.created_at === 'string'
                ? Date.parse(entry.created_at)
                : undefined;

            const validExplicitTimestamp =
              typeof explicitTimestamp === 'number' && !Number.isNaN(explicitTimestamp)
                ? explicitTimestamp
                : undefined;

            const inferredTimestamp =
              validExplicitTimestamp ??
              parseTimestampFromString(entry.filename || entry.file) ??
              parseTimestampFromString(matchId) ??
              undefined;

            return {
              ...entry,
              createdAtMs: inferredTimestamp,
              created_at: entry.created_at && typeof entry.created_at === 'number'
                ? entry.created_at
                : inferredTimestamp
                  ? Math.floor(inferredTimestamp / 1000)
                  : undefined,
            };
          });

          const totalSize = entries.reduce((sum, entry) => sum + entry.size_mb, 0);
          const timestamps = entries
            .map(entry => entry.createdAtMs ?? (entry.created_at ? entry.created_at * 1000 : undefined))
            .filter((value): value is number => Boolean(value));
          const firstTimestamp = timestamps.length > 0
            ? Math.min(...timestamps)
            : parseTimestampFromString(matchId) || Date.now();

          const cameraMap = new Map<string, number>();
          entries.forEach((entry) => {
            const key = getCameraKey(entry.file);
            const segmentsForEntry = entry.segment_count ?? 1;
            cameraMap.set(key, (cameraMap.get(key) ?? 0) + segmentsForEntry);
          });

          const cameraCount = cameraMap.size || (entries.length > 0 ? 1 : 0);
          const segmentsCount = Array.from(cameraMap.values()).reduce((sum, count) => sum + count, 0) || entries.length;

          return {
            id: matchId,
            files: entries,
            date: firstTimestamp,
            total_size_mb: totalSize,
            cameraCount,
            segmentsCount,
          };
        }
      );

      setMatches(matchList);
      setDebugInfo(`Loaded ${matchList.length} matches`);
    } catch (error) {
      console.error('Failed to load matches:', error);
      setDebugInfo(`Error: ${error}`);
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
    setSegmentDetails(null);
  };

  const handleDownloadModalClose = () => {
    setDownloadModalMatchId(null);
    setSegmentDetails(null);
    setSegmentsLoading(false);
  };

  useEffect(() => {
    if (!downloadModalMatchId) {
      return;
    }

    const match = matches.find(m => m.id === downloadModalMatchId);
    if (!match) {
      return;
    }

    const availableCameras = (['cam0', 'cam1'] as const).filter(camera =>
      match.files.some(entry => getCameraKey(entry.file) === camera)
    );

    if (availableCameras.length > 0) {
      setActiveCamera(prev => (availableCameras.includes(prev) ? prev : availableCameras[0]));
    }

    const requiresSegmentDetails = match.files.some(
      entry => entry.type === 'segmented' || (entry.segment_count && entry.segment_count > 1)
    );

    if (!requiresSegmentDetails) {
      setSegmentsLoading(false);
      setSegmentDetails(null);
      return;
    }

    let cancelled = false;
    const loadSegmentDetails = async () => {
      setSegmentsLoading(true);
      try {
        const response = await fetch(`/api/v1/recordings/${match.id}/segments`);
        if (!response.ok) {
          throw new Error(`Failed to load segment details (${response.status})`);
        }
        const data: SegmentDetails = await response.json();
        if (cancelled) {
          return;
        }
        const sortSegments = (segments: SegmentInfo[]) =>
          [...segments].sort((a, b) => a.segment_number - b.segment_number);
        setSegmentDetails({
          ...data,
          cam0: sortSegments(data.cam0 || []),
          cam1: sortSegments(data.cam1 || []),
        });
      } catch (error) {
        console.error('Failed to load segments:', error);
        if (!cancelled) {
          alert('Failed to load segment details');
        }
      } finally {
        if (!cancelled) {
          setSegmentsLoading(false);
        }
      }
    };

    loadSegmentDetails();

    return () => {
      cancelled = true;
    };
  }, [downloadModalMatchId, matches]);

  useEffect(() => {
    if (!segmentDetails) {
      return;
    }

    const available = (['cam0', 'cam1'] as const).filter(camera =>
      segmentDetails[camera] && segmentDetails[camera].length > 0
    );

    if (available.length > 0 && !available.includes(activeCamera)) {
      setActiveCamera(available[0]);
    }
  }, [segmentDetails, activeCamera]);

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
      {debugInfo && (
        <div className="mb-4 p-3 bg-yellow-100 border border-yellow-400 rounded text-sm font-mono">
          <strong>Debug:</strong> {debugInfo} | Loading: {loading ? 'true' : 'false'} | Matches: {matches.length} | Sorted: {sortedMatches.length}
        </div>
      )}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold">Matches</h1>
          <div className="mt-2 text-sm text-gray-600 flex flex-col sm:flex-row sm:items-center sm:gap-2">
            <span className="font-medium text-gray-700">Disk space:</span>
            {diskStatus ? (
              <span>
                {diskStatus.freeGb.toFixed(1)} GB free
                <span className="text-xs text-gray-500 ml-2">({diskStatus.percentUsed.toFixed(1)}% used)</span>
              </span>
            ) : (
              <span className="text-xs text-gray-500">Unavailable</span>
            )}
          </div>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <label className="flex items-center text-sm text-gray-600">
            <span className="mr-2">Sort by:</span>
            <select
              value={sortOption}
              onChange={(event) => setSortOption(event.target.value as typeof sortOption)}
              className="border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="date_desc">Newest first</option>
              <option value="date_asc">Oldest first</option>
              <option value="name_asc">Name A-Z</option>
              <option value="name_desc">Name Z-A</option>
              <option value="size_desc">Size high-low</option>
              <option value="size_asc">Size low-high</option>
            </select>
          </label>
          <button
            onClick={loadMatches}
            className="flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 touch-manipulation"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </button>
        </div>
      </div>

      {downloadModalMatchId && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
          onClick={handleDownloadModalClose}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-xl font-bold mb-2">Download Recording</h3>
            <p className="text-gray-600 mb-4">
              <strong>{downloadModalMatchId}</strong>
            </p>

            {hasSegmentedFiles && (
              <div className="mb-6">
                <h4 className="text-lg font-semibold text-gray-800 mb-2">Segmented Cameras</h4>
                <p className="text-sm text-gray-600 mb-3">Select a camera to view all available segments.</p>

                <div className="flex flex-wrap gap-2 mb-4">
                  {(['cam0', 'cam1'] as const).map(camera => {
                    const segmentCount = segmentDetails
                      ? segmentDetails[camera]?.length ?? 0
                      : cameraFileMap[camera]?.segment_count ?? 0;
                    const hasSegments = segmentCount > 0 || segmentsLoading;
                    const label = camera === 'cam0' ? 'Cam 0' : 'Cam 1';
                    const isActive = activeCamera === camera;

                    return (
                      <button
                        key={camera}
                        onClick={() => hasSegments && setActiveCamera(camera)}
                        className={`px-4 py-2 rounded border text-sm font-medium transition-colors touch-manipulation ${
                          isActive
                            ? 'bg-blue-600 text-white border-blue-600'
                            : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-100'
                        } ${!hasSegments ? 'opacity-60 cursor-not-allowed' : ''}`}
                        disabled={!hasSegments}
                      >
                        {label}
                        <span className="ml-2 text-xs font-normal">
                          {segmentsLoading && !segmentDetails ? 'Loading…' : `${segmentCount} segments`}
                        </span>
                      </button>
                    );
                  })}
                </div>

                {segmentsLoading && !segmentDetails ? (
                  <div className="py-6 text-center text-gray-500">Loading segments…</div>
                ) : (
                  <>
                    {cameraSegments.length > 0 ? (
                      <>
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <span className="text-sm font-medium text-gray-700">Total Segments:</span>
                              <span className="ml-2 text-lg font-bold text-blue-600">{cameraSegments.length}</span>
                            </div>
                            <div>
                              <span className="text-sm font-medium text-gray-700">Total Size:</span>
                              <span className="ml-2 text-lg font-bold text-blue-600">
                                {formatSize(cameraSegments.reduce((sum, s) => sum + s.size_mb, 0))}
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

                        <div className="mb-4">
                          <button
                            onClick={() => {
                              alert('Download all segments functionality coming soon');
                            }}
                            className="w-full flex items-center justify-center px-4 py-3 bg-green-600 text-white rounded hover:bg-green-700 font-medium touch-manipulation"
                          >
                            <Package className="w-5 h-5 mr-2" />
                            Download All Segments ({cameraSegments.length} files)
                          </button>
                        </div>

                        <div className="space-y-2">
                          <h5 className="text-sm font-semibold text-gray-700 mb-2">
                            {activeCamera === 'cam0' ? 'Camera 0' : 'Camera 1'} Segments
                          </h5>
                          {cameraSegments.map(segment => (
                            <div
                              key={segment.name}
                              className="flex items-center justify-between p-3 bg-gray-50 rounded border border-gray-200 hover:bg-gray-100"
                            >
                              <div className="flex-1">
                                <div className="font-medium text-sm">Segment {segment.segment_number + 1}</div>
                                <div className="text-xs text-gray-500">
                                  {formatSize(segment.size_mb)} • {formatTimestamp(segment.created_at)}
                                </div>
                              </div>
                              <a
                                href={segment.path}
                                download
                                className="flex items-center px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm touch-manipulation ml-2"
                              >
                                <Download className="w-4 h-4 mr-1" />
                                Download
                              </a>
                            </div>
                          ))}
                        </div>
                      </>
                    ) : (
                      <div className="p-4 text-center text-sm text-gray-500 bg-gray-50 border border-dashed border-gray-200 rounded">
                        No segments available for {activeCamera === 'cam0' ? 'Cam 0' : 'Cam 1'}.
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {singleFiles.length > 0 && (
              <div className="flex flex-col gap-2">
                <h4 className="text-lg font-semibold text-gray-800">Direct Downloads</h4>
                {singleFiles.map(entry => {
                  const createdLabel = formatTimestamp(entry.createdAtMs ?? (entry.created_at ? entry.created_at * 1000 : undefined));
                  return (
                    <a
                      key={entry.file}
                      href={`/recordings/${downloadModalMatchId}/segments/${entry.file}`}
                      download
                      className="flex items-center justify-between px-4 py-3 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm touch-manipulation"
                    >
                      <span className="flex flex-col text-left">
                        <span className="flex items-center">
                          <Download className="w-4 h-4 mr-2" />
                          {formatLabel(entry.file)}
                        </span>
                        <span className="text-xs text-gray-200 mt-1">{createdLabel}</span>
                      </span>
                      <span className="text-xs opacity-75">{formatSize(entry.size_mb)}</span>
                    </a>
                  );
                })}
              </div>
            )}

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
        {sortedMatches.map((match) => (
          <div key={match.id} className="bg-white rounded-lg shadow p-4 md:p-6">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold">{match.id}</h3>
                <p className="text-gray-600 text-sm">
                  {formatTimestamp(match.date)}
                </p>
                <p className="text-gray-500 text-xs mt-1">
                  {match.cameraCount} {match.cameraCount === 1 ? 'camera' : 'cameras'}
                  {match.segmentsCount > match.cameraCount && (
                    <span className="ml-1">• {match.segmentsCount} segments</span>
                  )}
                  <span className="ml-1">• {formatSize(match.total_size_mb)} total</span>
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
