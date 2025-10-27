import axios from 'axios';
import type {
  CameraConfig,
  AllCamerasConfig,
  CameraConfigUpdateRequest,
  CameraConfigUpdateResponse,
  Preset,
  PresetListItem,
  PresetSaveRequest,
  PresetSaveResponse,
  PresetLoadResponse,
  PresetDeleteResponse,
  ApplyConfigResponse,
} from '../types/camera';

const API_BASE_URL = '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ============================================================================
// API v3 Response Types (Updated for new in-process GStreamer architecture)
// ============================================================================

export interface RecordingStatusV3 {
  recording: boolean;
  match_id: string | null;
  duration: number;
  cameras: {
    camera_0?: {
      state: string;
      uptime: number;
    };
    camera_1?: {
      state: string;
      uptime: number;
    };
  };
  protected: boolean;
}

export interface PreviewStatusV3 {
  preview_active: boolean;
  cameras: {
    camera_0: {
      active: boolean;
      state: string;
      uptime: number;
      hls_url: string;
    };
    camera_1: {
      active: boolean;
      state: string;
      uptime: number;
      hls_url: string;
    };
  };
}

export interface StatusResponseV3 {
  recording: RecordingStatusV3;
  preview: PreviewStatusV3;
}

// Legacy types for backward compatibility
export interface RecordingStatus {
  status: 'idle' | 'recording';
  recording?: boolean;
  match_id?: string;
  duration_seconds?: number;
  cam0_running?: boolean;
  cam1_running?: boolean;
  mode?: string;
  mode_description?: string;
}

export interface RecordingRequest {
  match_id: string;
  force?: boolean;
  resolution?: string;  // Ignored by API v3
  fps?: number;  // Ignored by API v3
  bitrate_kbps?: number;  // Ignored by API v3
  mode?: 'normal' | 'no_crop' | 'optimized';  // Ignored by API v3
}

export interface RecordingStartResponseV3 {
  success: boolean;
  message: string;
  match_id: string;
  cameras_started: number[];
  cameras_failed: number[];
}

export interface RecordingStopResponseV3 {
  success: boolean;
  message: string;
  protected?: boolean;
}

// Legacy types
export interface RecordingStartResponse {
  status: string;
  match_id: string;
  cam0_pid: number;
  cam1_pid: number;
  start_time: string;
}

export interface RecordingStopResponse {
  status: string;
  match_id: string;
  duration_seconds: number;
  files: {
    cam0: string | null;
    cam1: string | null;
    cam0_size_mb: number;
    cam1_size_mb: number;
  };
}

export interface RecordingFile {
  file: string;
  size_mb: number;
}

export interface RecordingsResponse {
  recordings: Record<string, RecordingFile[]>;
}

export interface DeleteRecordingResponse {
  status: string;
  match_id: string;
  files_deleted: number;
  size_mb_freed: number;
}

export interface PreviewStatus {
  status: string;
  streaming: boolean;
  resolution?: string;
  framerate?: number;
  cam0_running?: boolean;
  cam1_running?: boolean;
  cam0_url?: string;
  cam1_url?: string;
}

export interface PreviewStartResponse {
  status: string;
  resolution: string;
  framerate: number;
  cam0_url: string;
  cam1_url: string;
  cam0_pid: number;
  cam1_pid: number;
  mode?: string;
  mode_description?: string;
}

export interface PreviewRequest {
  camera_id?: number | null;
  mode?: 'normal' | 'no_crop' | 'calibration';
}

// ============================================================================
// API Service
// ============================================================================

export const apiService = {
  /**
   * Get overall system status (API v3)
   * Returns recording and preview status
   */
  async getStatus(): Promise<RecordingStatus> {
    try {
      const response = await api.get<StatusResponseV3>('/status');
      const data = response.data;

      // Transform v3 response to legacy format for backward compatibility
      return {
        status: data.recording.recording ? 'recording' : 'idle',
        recording: data.recording.recording,
        match_id: data.recording.match_id || undefined,
        duration_seconds: data.recording.duration,
        cam0_running: (data.recording.cameras?.camera_0?.state === 'PLAYING' || data.recording.cameras?.camera_0?.state === 'running') || false,
        cam1_running: (data.recording.cameras?.camera_1?.state === 'PLAYING' || data.recording.cameras?.camera_1?.state === 'running') || false,
      };
    } catch (error) {
      console.error('Failed to get status:', error);
      // Return idle status on error
      return {
        status: 'idle',
        recording: false,
      };
    }
  },

  /**
   * Start recording (API v3)
   * Resolution/FPS/bitrate are hardcoded in backend (2880x1620, 30fps, 12Mbps)
   */
  async startRecording(request: RecordingRequest): Promise<RecordingStartResponse> {
    const v3Request = {
      match_id: request.match_id,
      force: request.force || false,
    };

    const response = await api.post<RecordingStartResponseV3>('/recording', v3Request);
    const data = response.data;

    // Transform v3 response to legacy format
    return {
      status: data.success ? 'started' : 'failed',
      match_id: data.match_id,
      cam0_pid: data.cameras_started.includes(0) ? 1 : 0,  // Fake PIDs for compatibility
      cam1_pid: data.cameras_started.includes(1) ? 1 : 0,
      start_time: new Date().toISOString(),
    };
  },

  /**
   * Stop recording (API v3)
   * Note: Duration info is not returned by v3 API, need to track in UI
   */
  async stopRecording(): Promise<RecordingStopResponse> {
    // Get current status to retrieve duration before stopping
    let currentStatus: RecordingStatus | null = null;
    try {
      currentStatus = await this.getStatus();
    } catch (e) {
      console.warn('Could not get status before stopping');
    }

    const response = await api.delete<RecordingStopResponseV3>('/recording');
    const data = response.data;

    if (!data.success) {
      throw new Error(data.message || 'Failed to stop recording');
    }

    // Transform v3 response to legacy format
    return {
      status: 'stopped',
      match_id: currentStatus?.match_id || 'unknown',
      duration_seconds: currentStatus?.duration_seconds || 0,
      files: {
        cam0: null,  // File info not available in v3 response
        cam1: null,
        cam0_size_mb: 0,
        cam1_size_mb: 0,
      },
    };
  },

  /**
   * Get all recordings
   * Note: Not implemented in API v3 - returns empty for now
   */
  async getRecordings(): Promise<RecordingsResponse> {
    const response = await api.get<RecordingsResponse>('/recordings');
    
    return response.data;
  },

  /**
   * Delete a recording
   * Note: Not implemented in API v3
   */
  async deleteRecording(matchId: string): Promise<DeleteRecordingResponse> {
    const response = await api.delete<DeleteRecordingResponse>(`/recordings/${matchId}`);
    return response.data;
  },

  // ========================================================================
  // Preview endpoints (API v3)
  // ========================================================================

  async getPreviewStatus(): Promise<PreviewStatus> {
    try {
      const statusResponse = await api.get<StatusResponseV3>('/status');
      const preview = statusResponse.data.preview;

      return {
        status: preview.preview_active ? 'streaming' : 'idle',
        streaming: preview.preview_active,
        cam0_running: preview.cameras.camera_0.active,
        cam1_running: preview.cameras.camera_1.active,
        cam0_url: preview.cameras.camera_0.hls_url,
        cam1_url: preview.cameras.camera_1.hls_url,
      };
    } catch (error) {
      console.error('Failed to get preview status:', error);
      return {
        status: 'idle',
        streaming: false,
      };
    }
  },

  async startPreview(request?: PreviewRequest): Promise<PreviewStartResponse> {
    const response = await api.post('/preview', {
      camera_id: request?.camera_id ?? null,
    });

    const data = response.data;

    // Transform to legacy format
    return {
      status: data.success ? 'started' : 'failed',
      resolution: '2880x1620',  // Hardcoded in v3
      framerate: 30,
      cam0_url: '/hls/cam0.m3u8',
      cam1_url: '/hls/cam1.m3u8',
      cam0_pid: 1,  // Fake PIDs
      cam1_pid: 1,
    };
  },

  async stopPreview(): Promise<{ status: string }> {
    await api.delete('/preview');
    return { status: 'stopped' };
  },

  // ========================================================================
  // Camera configuration endpoints (unchanged, not part of v3 core)
  // ========================================================================

  async getAllCameraConfigs(): Promise<AllCamerasConfig> {
    const response = await api.get<AllCamerasConfig>('/camera/config');
    return response.data;
  },

  async getCameraConfig(cameraId: number): Promise<CameraConfig> {
    const response = await api.get<CameraConfig>(`/camera/config/${cameraId}`);
    return response.data;
  },

  async updateCameraConfig(
    cameraId: number,
    config: CameraConfigUpdateRequest
  ): Promise<CameraConfigUpdateResponse> {
    const response = await api.post<CameraConfigUpdateResponse>(
      `/camera/config/${cameraId}`,
      config
    );
    return response.data;
  },

  async applyCameraConfig(): Promise<ApplyConfigResponse> {
    const response = await api.post<ApplyConfigResponse>('/camera/apply');
    return response.data;
  },

  // ========================================================================
  // Preset endpoints (unchanged)
  // ========================================================================

  async listPresets(): Promise<PresetListItem[]> {
    const response = await api.get<PresetListItem[]>('/camera/presets');
    return response.data;
  },

  async getPreset(name: string): Promise<Preset> {
    const response = await api.get<Preset>(`/camera/presets/${name}`);
    return response.data;
  },

  async savePreset(name: string, request: PresetSaveRequest): Promise<PresetSaveResponse> {
    const response = await api.post<PresetSaveResponse>(
      `/camera/presets/${name}`,
      request
    );
    return response.data;
  },

  async loadPreset(name: string): Promise<PresetLoadResponse> {
    const response = await api.post<PresetLoadResponse>(
      `/camera/presets/${name}/load`
    );
    return response.data;
  },

  async deletePreset(name: string): Promise<PresetDeleteResponse> {
    const response = await api.delete<PresetDeleteResponse>(
      `/camera/presets/${name}`
    );
    return response.data;
  },

  // Development API methods
  async getDevStatus(): Promise<any> {
    const response = await api.get('/dev/status');
    return response.data;
  },

  async getGitStatus(): Promise<any> {
    const response = await api.get('/dev/git-status');
    return response.data;
  },

  async gitPull(): Promise<any> {
    const response = await api.post('/dev/git-pull');
    return response.data;
  },

  async buildDevUI(): Promise<any> {
    const response = await api.post('/dev/build-ui');
    return response.data;
  },

  async switchService(target: 'dev' | 'prod'): Promise<any> {
    const response = await api.post('/dev/switch-service', { target });
    return response.data;
  },

  async restartProduction(): Promise<any> {
    const response = await api.post('/dev/restart-production');
    return response.data;
  },

  async getServiceStatus(): Promise<any> {
    const response = await api.get('/dev/service-status');
    return response.data;
  },

  async deployToProduction(confirm: boolean): Promise<any> {
    const response = await api.post('/dev/deploy-prod', { confirm });
    return response.data;
  },

  async listBackups(): Promise<any> {
    const response = await api.get('/dev/backups');
    return response.data;
  },

  async rollback(backupName: string): Promise<any> {
    const response = await api.post('/dev/rollback', { backup_name: backupName });
    return response.data;
  },

  async getDevLogs(service: 'dev' | 'prod', lines: number = 100): Promise<any> {
    const response = await api.get(`/dev/logs?service=${service}&lines=${lines}`);
    return response.data;
  },

  async getSystemInfo(): Promise<any> {
    const response = await api.get('/dev/system-info');
    return response.data;
  },
};
