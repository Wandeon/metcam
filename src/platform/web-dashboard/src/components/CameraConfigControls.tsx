import { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import type {
  CameraConfig,
  CorrectionType,
  PresetListItem,
} from '../types/camera';

interface CameraConfigControlsProps {
  onApply?: () => void;
}

export const CameraConfigControls = ({ onApply }: CameraConfigControlsProps) => {
  const [config0, setConfig0] = useState<CameraConfig | null>(null);
  const [config1, setConfig1] = useState<CameraConfig | null>(null);
  const [presets, setPresets] = useState<PresetListItem[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<string>('');
  const [newPresetName, setNewPresetName] = useState('');
  const [newPresetDesc, setNewPresetDesc] = useState('');
  const [isApplying, setIsApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPresetDialog, setShowPresetDialog] = useState(false);

  // Load camera configs on mount
  useEffect(() => {
    loadConfigs();
    loadPresets();
  }, []);

  const loadConfigs = async () => {
    try {
      const data0 = await apiService.getCameraConfig(0);
      const data1 = await apiService.getCameraConfig(1);
      setConfig0(data0);
      setConfig1(data1);
      setError(null);
    } catch (err) {
      setError('Failed to load camera configurations');
      console.error(err);
    }
  };

  const loadPresets = async () => {
    try {
      const data = await apiService.listPresets();
      setPresets(data);
    } catch (err) {
      console.error('Failed to load presets:', err);
    }
  };

  const handleApply = async () => {
    if (!config0 || !config1) return;

    setIsApplying(true);
    setError(null);

    try {
      // Update both camera configs
      await apiService.updateCameraConfig(0, config0);
      await apiService.updateCameraConfig(1, config1);

      // Apply config (restart preview)
      await apiService.applyCameraConfig();

      if (onApply) {
        onApply();
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to apply configuration');
      console.error(err);
    } finally {
      setIsApplying(false);
    }
  };

  const handlePresetLoad = async () => {
    if (!selectedPreset) return;

    try {
      await apiService.loadPreset(selectedPreset);
      await loadConfigs();  // Reload configs
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load preset');
      console.error(err);
    }
  };

  const handlePresetSave = async () => {
    if (!newPresetName.trim()) {
      setError('Preset name is required');
      return;
    }

    try {
      await apiService.savePreset(newPresetName, {
        description: newPresetDesc,
      });
      await loadPresets();
      setNewPresetName('');
      setNewPresetDesc('');
      setShowPresetDialog(false);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save preset');
      console.error(err);
    }
  };

  const handlePresetDelete = async () => {
    if (!selectedPreset) return;

    if (!confirm(`Delete preset "${selectedPreset}"?`)) return;

    try {
      await apiService.deletePreset(selectedPreset);
      await loadPresets();
      setSelectedPreset('');
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete preset');
      console.error(err);
    }
  };

  if (!config0 || !config1) {
    return (
      <div className="p-4 bg-gray-100 rounded">
        <p className="text-gray-600">Loading camera configurations...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="p-3 bg-red-100 border border-red-400 text-red-700 rounded">
          {error}
        </div>
      )}

      {/* Camera Controls Side by Side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Camera 0 */}
        <CameraControls
          cameraId={0}
          config={config0}
          onChange={setConfig0}
        />

        {/* Camera 1 */}
        <CameraControls
          cameraId={1}
          config={config1}
          onChange={setConfig1}
        />
      </div>

      {/* Preset Management - Single Section */}
      <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
        <h3 className="text-lg font-semibold mb-3">Presets</h3>

        <div className="flex gap-2 mb-3">
          <select
            value={selectedPreset}
            onChange={(e) => setSelectedPreset(e.target.value)}
            className="flex-1 px-3 py-2 border rounded"
          >
            <option value="">Select preset...</option>
            {presets.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name} - {p.description}
              </option>
            ))}
          </select>
          <button
            onClick={handlePresetLoad}
            disabled={!selectedPreset}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-300"
          >
            Load
          </button>
          <button
            onClick={handlePresetDelete}
            disabled={!selectedPreset}
            className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 disabled:bg-gray-300"
          >
            Delete
          </button>
        </div>

        <button
          onClick={() => setShowPresetDialog(true)}
          className="w-full px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
        >
          Save Current as New Preset
        </button>

        {/* Save Preset Dialog */}
        {showPresetDialog && (
          <div className="mt-3 p-3 bg-green-50 border border-green-300 rounded">
            <p className="text-sm font-medium mb-2">Save Preset</p>
            <input
              type="text"
              placeholder="Preset name"
              value={newPresetName}
              onChange={(e) => setNewPresetName(e.target.value)}
              className="w-full px-3 py-2 border rounded mb-2"
            />
            <input
              type="text"
              placeholder="Description (optional)"
              value={newPresetDesc}
              onChange={(e) => setNewPresetDesc(e.target.value)}
              className="w-full px-3 py-2 border rounded mb-2"
            />
            <div className="flex gap-2">
              <button
                onClick={handlePresetSave}
                className="flex-1 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
              >
                Save
              </button>
              <button
                onClick={() => setShowPresetDialog(false)}
                className="flex-1 px-4 py-2 bg-gray-400 text-white rounded hover:bg-gray-500"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Single Apply Button */}
      <button
        onClick={handleApply}
        disabled={isApplying}
        className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold text-lg hover:bg-blue-700 disabled:bg-gray-400"
      >
        {isApplying ? 'Applying Configuration...' : 'Apply Configuration to Both Cameras'}
      </button>
    </div>
  );
};

// Individual Camera Controls Component
interface CameraControlsProps {
  cameraId: number;
  config: CameraConfig;
  onChange: (config: CameraConfig) => void;
}

const CameraControls = ({ cameraId, config, onChange }: CameraControlsProps) => {
  return (
    <div className="p-4 bg-white rounded-lg shadow border border-gray-200">
      <h3 className="text-lg font-semibold mb-4">Camera {cameraId}</h3>

      {/* Rotation - Text Input */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">
          Rotation (degrees)
        </label>
        <input
          type="number"
          step="0.1"
          min="-180"
          max="180"
          value={config.rotation}
          onChange={(e) =>
            onChange({ ...config, rotation: parseFloat(e.target.value) || 0 })
          }
          className="w-full px-3 py-2 border rounded"
        />
        <p className="text-xs text-gray-500 mt-1">Range: -180° to +180°</p>
      </div>

      {/* Crop Controls */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">
          Crop (pixels) - Output: 2880×1620
        </label>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-xs text-gray-600">Left</label>
            <input
              type="number"
              value={config.crop.left}
              onChange={(e) => {
                const newLeft = parseInt(e.target.value) || 0;
                const delta = newLeft - config.crop.left;
                const newRight = Math.max(0, config.crop.right - delta);
                onChange({
                  ...config,
                  crop: { ...config.crop, left: newLeft, right: newRight },
                });
              }}
              className="w-full px-2 py-1 border rounded text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-gray-600">Right</label>
            <input
              type="number"
              value={config.crop.right}
              onChange={(e) => {
                const newRight = parseInt(e.target.value) || 0;
                const delta = newRight - config.crop.right;
                const newLeft = Math.max(0, config.crop.left - delta);
                onChange({
                  ...config,
                  crop: { ...config.crop, left: newLeft, right: newRight },
                });
              }}
              className="w-full px-2 py-1 border rounded text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-gray-600">Top</label>
            <input
              type="number"
              value={config.crop.top}
              onChange={(e) => {
                const newTop = parseInt(e.target.value) || 0;
                const delta = newTop - config.crop.top;
                const newBottom = Math.max(0, config.crop.bottom - delta);
                onChange({
                  ...config,
                  crop: { ...config.crop, top: newTop, bottom: newBottom },
                });
              }}
              className="w-full px-2 py-1 border rounded text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-gray-600">Bottom</label>
            <input
              type="number"
              value={config.crop.bottom}
              onChange={(e) => {
                const newBottom = parseInt(e.target.value) || 0;
                const delta = newBottom - config.crop.bottom;
                const newTop = Math.max(0, config.crop.top - delta);
                onChange({
                  ...config,
                  crop: { ...config.crop, top: newTop, bottom: newBottom },
                });
              }}
              className="w-full px-2 py-1 border rounded text-sm"
            />
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-1">
          Width: {3840 - config.crop.left - config.crop.right}px,
          Height: {2160 - config.crop.top - config.crop.bottom}px
        </p>
      </div>

      {/* Correction Type */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">Correction Type</label>
        <select
          value={config.correction_type}
          onChange={(e) => {
            const newType = e.target.value as CorrectionType;
            // Get default params for new correction type
            let newParams: any = {};
            if (newType === 'barrel') {
              newParams = { k1: 0.15, k2: 0.05 };
            } else if (newType === 'cylindrical') {
              newParams = { radius: 1.0, axis: 'horizontal' };
            } else if (newType === 'equirectangular') {
              newParams = { fov_h: 120, fov_v: 90, center_x: 0.5, center_y: 0.5 };
            } else if (newType === 'perspective') {
              newParams = { corners: [[0, 0], [1, 0], [1, 1], [0, 1]] };
            }

            onChange({
              ...config,
              correction_type: newType,
              correction_params: newParams,
            });
          }}
          className="w-full px-3 py-2 border rounded"
        >
          <option value="barrel">Barrel (Radial Distortion)</option>
          <option value="cylindrical">Cylindrical Projection</option>
          <option value="equirectangular">Equirectangular (Spherical)</option>
          <option value="perspective">Perspective Transform</option>
        </select>
      </div>

      {/* Correction Parameters */}
      {config.correction_type === 'barrel' && (
        <div className="p-3 bg-gray-50 rounded">
          <p className="text-sm font-medium mb-2">Barrel Parameters</p>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-gray-600">k1 (Quadratic)</label>
              <input
                type="number"
                step="0.01"
                min="-1"
                max="1"
                value={(config.correction_params as any).k1 || 0}
                onChange={(e) =>
                  onChange({
                    ...config,
                    correction_params: {
                      ...config.correction_params,
                      k1: parseFloat(e.target.value) || 0,
                    },
                  })
                }
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-gray-600">k2 (Quartic)</label>
              <input
                type="number"
                step="0.01"
                min="-1"
                max="1"
                value={(config.correction_params as any).k2 || 0}
                onChange={(e) =>
                  onChange({
                    ...config,
                    correction_params: {
                      ...config.correction_params,
                      k2: parseFloat(e.target.value) || 0,
                    },
                  })
                }
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
          </div>
        </div>
      )}

      {config.correction_type === 'cylindrical' && (
        <div className="p-3 bg-gray-50 rounded">
          <p className="text-sm font-medium mb-2">Cylindrical Parameters</p>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-gray-600">Radius</label>
              <input
                type="number"
                step="0.1"
                min="0.1"
                max="5"
                value={(config.correction_params as any).radius || 1.0}
                onChange={(e) =>
                  onChange({
                    ...config,
                    correction_params: {
                      ...config.correction_params,
                      radius: parseFloat(e.target.value) || 1.0,
                    },
                  })
                }
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-gray-600">Axis</label>
              <select
                value={(config.correction_params as any).axis || 'horizontal'}
                onChange={(e) =>
                  onChange({
                    ...config,
                    correction_params: {
                      ...config.correction_params,
                      axis: e.target.value as 'horizontal' | 'vertical',
                    },
                  })
                }
                className="w-full px-2 py-1 border rounded text-sm"
              >
                <option value="horizontal">Horizontal</option>
                <option value="vertical">Vertical</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {config.correction_type === 'equirectangular' && (
        <div className="p-3 bg-gray-50 rounded">
          <p className="text-sm font-medium mb-2">Equirectangular Parameters</p>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-gray-600">FOV Horizontal (°)</label>
              <input
                type="number"
                min="10"
                max="360"
                value={(config.correction_params as any).fov_h || 120}
                onChange={(e) =>
                  onChange({
                    ...config,
                    correction_params: {
                      ...config.correction_params,
                      fov_h: parseInt(e.target.value) || 120,
                    },
                  })
                }
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-gray-600">FOV Vertical (°)</label>
              <input
                type="number"
                min="10"
                max="180"
                value={(config.correction_params as any).fov_v || 90}
                onChange={(e) =>
                  onChange({
                    ...config,
                    correction_params: {
                      ...config.correction_params,
                      fov_v: parseInt(e.target.value) || 90,
                    },
                  })
                }
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
