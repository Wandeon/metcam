import axios from 'axios';

const API_BASE_URL = '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface RecordingStatus {
  status: 'idle' | 'recording';
  match_id?: string;
  duration_seconds?: number;
  cam0_running?: boolean;
  cam1_running?: boolean;
}

export interface RecordingRequest {
  match_id: string;
  resolution?: string;
  fps?: number;
  bitrate?: number;
}

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
}

export const apiService = {
  async getStatus(): Promise<RecordingStatus> {
    const response = await api.get<RecordingStatus>('/status');
    return response.data;
  },

  async startRecording(request: RecordingRequest): Promise<RecordingStartResponse> {
    const response = await api.post<RecordingStartResponse>('/recording', request);
    return response.data;
  },

  async stopRecording(): Promise<RecordingStopResponse> {
    const response = await api.delete<RecordingStopResponse>('/recording');
    return response.data;
  },

  async getRecordings(): Promise<RecordingsResponse> {
    const response = await api.get<RecordingsResponse>('/recordings');
    return response.data;
  },

  // Preview endpoints
  async getPreviewStatus(): Promise<PreviewStatus> {
    const response = await api.get<PreviewStatus>('/preview/status');
    return response.data;
  },

  async startPreview(): Promise<PreviewStartResponse> {
    const response = await api.post<PreviewStartResponse>('/preview/start');
    return response.data;
  },

  async stopPreview(): Promise<{ status: string }> {
    const response = await api.post<{ status: string }>('/preview/stop');
    return response.data;
  },
};
