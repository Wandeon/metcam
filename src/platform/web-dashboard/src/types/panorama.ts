/**
 * Panorama Stitching API Types
 * TypeScript types for panorama preview, calibration, and post-processing
 */

// ============================================================================
// Status & Performance Types
// ============================================================================

/**
 * Real-time performance metrics for panorama stitching
 */
export interface PanoramaPerformance {
  current_fps: number;
  frames_stitched: number;
  sync_stats: SyncStats;
  stitch_stats: StitchStats;
}

/**
 * Frame synchronization statistics
 */
export interface SyncStats {
  avg_sync_drift_ms?: number;
  dropped_frames?: number;
  max_drift_ms?: number;
  sync_quality?: number;
}

/**
 * Stitching performance statistics
 */
export interface StitchStats {
  avg_stitch_time_ms?: number;
  gpu_utilization?: number;
  vpi_backend?: string;
}

/**
 * Calibration information embedded in status
 */
export interface CalibrationInfo {
  calibration_date: string | null;
  quality_score: number;
  reprojection_error: number;
}

/**
 * Panorama configuration settings
 */
export interface PanoramaConfig {
  enabled?: boolean;
  output_width?: number;
  output_height?: number;
  preview_fps_target?: number;
  use_vic_backend?: boolean;
  calibration?: CalibrationData;
}

/**
 * Complete calibration data structure
 */
export interface CalibrationData {
  calibration_date: string;
  quality_score: number;
  reprojection_error: number;
  homography_matrix?: number[][];
  transform_parameters?: unknown;
}

/**
 * Response from GET /panorama/status
 * Returns current state of panorama service
 */
export interface PanoramaStatus {
  preview_active: boolean;
  uptime_seconds: number;
  calibrated: boolean;
  calibration_info: CalibrationInfo;
  performance: PanoramaPerformance;
  config: PanoramaConfig;
}

/**
 * Response from GET /panorama/stats
 * Returns performance statistics
 */
export interface PanoramaStats {
  preview_active: boolean;
  uptime_seconds: number;
  current_fps: number;
  frames_stitched: number;
  sync_stats: SyncStats;
  stitch_stats: StitchStats;
}

// ============================================================================
// Calibration Types
// ============================================================================

/**
 * Response from GET /panorama/calibration
 * Returns calibration status and info
 */
export interface CalibrationStatus {
  calibrated: boolean;
  calibration_info: CalibrationInfo;
}

/**
 * Request for POST /panorama/calibration/start
 */
export interface CalibrationStartRequest {
  frame_count?: number; // Target number of frame pairs (default: 15)
}

/**
 * Response from POST /panorama/calibration/start
 */
export interface CalibrationStartResponse {
  success: boolean;
  message: string;
}

/**
 * Response from POST /panorama/calibration/capture
 * Returns progress information after capturing a frame pair
 */
export interface CalibrationProgress {
  success: boolean;
  message: string;
  frames_captured?: number;
  frames_needed?: number;
  progress_percent?: number;
}

/**
 * Response from POST /panorama/calibration/complete
 * Returns calibration result with quality metrics
 */
export interface CalibrationResult {
  success: boolean;
  message: string;
  calibration_date?: string;
  quality_score?: number;
  reprojection_error?: number;
  homography_matrix?: number[][];
}

/**
 * Response from DELETE /panorama/calibration
 */
export interface CalibrationClearResponse {
  success: boolean;
  message: string;
}

// ============================================================================
// Preview Types
// ============================================================================

/**
 * Response from POST /panorama/preview/start
 * Returns HLS stream URL and settings
 */
export interface PreviewResponse {
  success: boolean;
  message: string;
  hls_url?: string;
  resolution?: string;
  fps_target?: number;
  error_code?: 'NOT_CALIBRATED' | 'RECORDING_ACTIVE' | 'STITCHER_INIT_FAILED';
}

/**
 * Response from POST /panorama/preview/stop
 */
export interface PreviewStopResponse {
  success: boolean;
  message: string;
}

// ============================================================================
// Post-Processing Types
// ============================================================================

/**
 * Request for POST /panorama/process
 * Initiates post-processing of a recorded match
 */
export interface ProcessRecordingRequest {
  match_id: string;
}

/**
 * Response from POST /panorama/process
 */
export interface ProcessRecordingResponse {
  success: boolean;
  message: string;
  match_id?: string;
  cam0_segments?: number;
  cam1_segments?: number;
  estimated_duration_minutes?: number;
  error_code?: 'NOT_CALIBRATED' | 'MATCH_NOT_FOUND' | 'NO_SEGMENTS';
}

/**
 * Response from GET /panorama/process/{match_id}/status
 * Returns current processing progress
 */
export interface ProcessingStatus {
  processing: boolean;
  progress: number; // Percentage 0-100
  estimated_remaining_minutes: number;
  current_fps: number;
  message: string;
}

// ============================================================================
// Configuration Update Types
// ============================================================================

/**
 * Request for PUT /panorama/config
 * Updates panorama configuration settings
 */
export interface ConfigUpdateRequest {
  enabled?: boolean;
  output_width?: number;
  output_height?: number;
  preview_fps_target?: number;
  use_vic_backend?: boolean;
}

/**
 * Response from PUT /panorama/config
 */
export interface ConfigUpdateResponse {
  success: boolean;
  message: string;
  requested_updates?: ConfigUpdateRequest;
}

// ============================================================================
// Generic API Response Types
// ============================================================================

/**
 * Generic success response
 * Used by endpoints that return simple success/failure
 */
export interface ApiResponse {
  success: boolean;
  message: string;
}

/**
 * Generic error response
 * Follows FastAPI HTTPException format
 */
export interface ApiError {
  detail: string;
}

// ============================================================================
// Utility Types
// ============================================================================

/**
 * Error codes returned by panorama endpoints
 */
export type PanoramaErrorCode =
  | 'NOT_CALIBRATED'
  | 'RECORDING_ACTIVE'
  | 'STITCHER_INIT_FAILED'
  | 'MATCH_NOT_FOUND'
  | 'NO_SEGMENTS'
  | 'PREVIEW_ACTIVE'
  | 'CALIBRATION_NOT_STARTED';

/**
 * Panorama service states
 */
export type PanoramaState =
  | 'idle'
  | 'preview_active'
  | 'calibrating'
  | 'processing'
  | 'error';

// ============================================================================
// Constants
// ============================================================================

/**
 * Default configuration values
 */
export const PANORAMA_DEFAULTS = {
  output_width: 3840,
  output_height: 1315,
  preview_fps_target: 15,
  calibration_frame_count: 15,
  use_vic_backend: true,
} as const;

/**
 * HLS stream paths
 */
export const PANORAMA_STREAMS = {
  preview: '/hls/panorama.m3u8',
} as const;

/**
 * Processing state descriptions
 */
export const PROCESSING_STATES: Record<PanoramaState, string> = {
  idle: 'Panorama service idle',
  preview_active: 'Real-time preview active',
  calibrating: 'Calibration in progress',
  processing: 'Post-processing recording',
  error: 'Service error',
} as const;
