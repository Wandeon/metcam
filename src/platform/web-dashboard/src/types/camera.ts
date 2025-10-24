/**
 * Camera Configuration Types
 * TypeScript types for camera settings, distortion correction, and presets
 */

export interface CropConfig {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

export type CorrectionType = 'barrel' | 'cylindrical' | 'equirectangular' | 'perspective';

// Barrel distortion correction parameters
export interface BarrelCorrectionParams {
  k1: number;  // Quadratic distortion coefficient
  k2: number;  // Quartic distortion coefficient
}

// Cylindrical projection parameters
export interface CylindricalCorrectionParams {
  radius: number;  // Cylinder radius (affects curvature, typical: 0.5-2.0)
  axis: 'horizontal' | 'vertical';  // Cylinder axis orientation
}

// Equirectangular (spherical) projection parameters
export interface EquirectangularCorrectionParams {
  fov_h: number;     // Horizontal field of view in degrees (typical: 90-180)
  fov_v: number;     // Vertical field of view in degrees (typical: 60-120)
  center_x: number;  // Horizontal center offset (0.5 = centered)
  center_y: number;  // Vertical center offset (0.5 = centered)
}

// Perspective transform (keystone correction) parameters
export interface PerspectiveCorrectionParams {
  corners: [
    [number, number],  // Top-left corner (x, y) in normalized coords (0.0-1.0)
    [number, number],  // Top-right corner
    [number, number],  // Bottom-right corner
    [number, number]   // Bottom-left corner
  ];
}

// Union type for all correction parameters
export type CorrectionParams =
  | BarrelCorrectionParams
  | CylindricalCorrectionParams
  | EquirectangularCorrectionParams
  | PerspectiveCorrectionParams;

export interface CameraConfig {
  rotation: number;                    // Rotation angle in degrees
  crop: CropConfig;                    // Crop pixels on each side
  correction_type: CorrectionType;     // Type of distortion correction
  correction_params: CorrectionParams; // Parameters for the correction type
}

export interface AllCamerasConfig {
  [cameraId: string]: CameraConfig;  // Camera ID as key (e.g., "0", "1")
}

export interface Preset {
  name: string;
  description: string;
  cameras?: AllCamerasConfig;  // Optional - only present in full preset data
}

export interface PresetListItem {
  name: string;
  description: string;
}

// API Request/Response types

export interface CameraConfigUpdateRequest {
  rotation?: number;
  crop?: CropConfig;
  correction_type?: CorrectionType;
  correction_params?: Partial<CorrectionParams>;
}

export interface CameraConfigUpdateResponse {
  status: 'success' | 'error';
  camera_id: number;
  config: CameraConfig;
}

export interface PresetSaveRequest {
  description?: string;
}

export interface PresetSaveResponse {
  status: 'success' | 'error';
  preset_name: string;
  description: string;
}

export interface PresetLoadResponse {
  status: 'success' | 'error';
  preset_loaded: string;
  preview_restarted: boolean;
  message?: string;
}

export interface PresetDeleteResponse {
  status: 'success' | 'error';
  preset_deleted: string;
}

export interface ApplyConfigResponse {
  status: 'applied' | 'error';
  preview_restarted: boolean;
  message: string;
}

// Parameter ranges and defaults for UI validation

export const PARAMETER_RANGES = {
  rotation: { min: -180, max: 180, default: 0, step: 0.1 },
  crop: {
    left: { min: 0, max: 1920, default: 480, step: 1 },
    right: { min: 0, max: 1920, default: 480, step: 1 },
    top: { min: 0, max: 1080, default: 270, step: 1 },
    bottom: { min: 0, max: 1080, default: 270, step: 1 },
  },
  barrel: {
    k1: { min: -1.0, max: 1.0, default: 0.15, step: 0.01 },
    k2: { min: -1.0, max: 1.0, default: 0.05, step: 0.01 },
  },
  cylindrical: {
    radius: { min: 0.1, max: 5.0, default: 1.0, step: 0.1 },
  },
  equirectangular: {
    fov_h: { min: 10, max: 360, default: 120, step: 1 },
    fov_v: { min: 10, max: 180, default: 90, step: 1 },
    center_x: { min: 0.0, max: 1.0, default: 0.5, step: 0.01 },
    center_y: { min: 0.0, max: 1.0, default: 0.5, step: 0.01 },
  },
  perspective: {
    corner: { min: 0.0, max: 1.0, default: 0.0, step: 0.01 },
  },
} as const;

export const DEFAULT_CONFIGS: Record<CorrectionType, CorrectionParams> = {
  barrel: {
    k1: 0.15,
    k2: 0.05,
  },
  cylindrical: {
    radius: 1.0,
    axis: 'horizontal',
  },
  equirectangular: {
    fov_h: 120,
    fov_v: 90,
    center_x: 0.5,
    center_y: 0.5,
  },
  perspective: {
    corners: [
      [0.0, 0.0],
      [1.0, 0.0],
      [1.0, 1.0],
      [0.0, 1.0],
    ],
  },
};
