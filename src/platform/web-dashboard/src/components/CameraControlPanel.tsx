import { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import type {
  CameraConfig,
  CorrectionType,
  PresetListItem,
} from '../types/camera';

interface CameraControlPanelProps {
  cameraId: number;
  onApply?: () => void;
}

export const CameraControlPanel = ({ cameraId, onApply }: CameraControlPanelProps) => {
  const [config, setConfig] = useState<CameraConfig | null>(null);
  const [presets, setPresets] = useState<PresetListItem[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<string>('');
  const [newPresetName, setNewPresetName] = useState('');
  const [newPresetDesc, setNewPresetDesc] = useState('');
  const [isApplying, setIsApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPresetDialog, setShowPresetDialog] = useState(false);

  // Load camera config on mount
  useEffect(() => {
    loadConfig();
    loadPresets();
  }, [cameraId]);

  const loadConfig = async () => {
    try {
      const data = await apiService.getCameraConfig(cameraId);
      setConfig(data);
      setError(null);
    } catch (err) {
      setError(`Failed to load camera ${cameraId} config`);
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
    if (!config) return;

    setIsApplying(true);
    setError(null);

    try {
      // Update config
      await apiService.updateCameraConfig(cameraId, config);

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
      await loadConfig();  // Reload config
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

  if (!config) {
    return (
      <div className="p-4 bg-gray-100 rounded">
        <p className="text-gray-600">Loading camera {cameraId} configuration...</p>
      </div>
    );
  }

  return (
    <div className="p-4 bg-white rounded-lg shadow-sm border border-gray-200">
      <h3 className="text-lg font-semibold mb-4">Camera {cameraId} Settings</h3>

      {error && (
        <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
          {error}
        </div>
      )}

      {/* Rotation */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">
          Rotation: {config.rotation.toFixed(1)}°
        </label>
        <input
          type="range"
          min="-180"
          max="180"
          step="0.1"
          value={config.rotation}
          onChange={(e) =>
            setConfig({ ...config, rotation: parseFloat(e.target.value) })
          }
          className="w-full"
        />
      </div>

      {/* Crop Controls */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">Crop (pixels)</label>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-xs text-gray-600">Left</label>
            <input
              type="number"
              value={config.crop.left}
              onChange={(e) =>
                setConfig({
                  ...config,
                  crop: { ...config.crop, left: parseInt(e.target.value) },
                })
              }
              className="w-full px-2 py-1 border rounded text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-gray-600">Right</label>
            <input
              type="number"
              value={config.crop.right}
              onChange={(e) =>
                setConfig({
                  ...config,
                  crop: { ...config.crop, right: parseInt(e.target.value) },
                })
              }
              className="w-full px-2 py-1 border rounded text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-gray-600">Top</label>
            <input
              type="number"
              value={config.crop.top}
              onChange={(e) =>
                setConfig({
                  ...config,
                  crop: { ...config.crop, top: parseInt(e.target.value) },
                })
              }
              className="w-full px-2 py-1 border rounded text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-gray-600">Bottom</label>
            <input
              type="number"
              value={config.crop.bottom}
              onChange={(e) =>
                setConfig({
                  ...config,
                  crop: { ...config.crop, bottom: parseInt(e.target.value) },
                })
              }
              className="w-full px-2 py-1 border rounded text-sm"
            />
          </div>
        </div>
      </div>

      {/* Correction Type */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">Correction Type</label>
        <select
          value={config.correction_type}
          onChange={(e) =>
            setConfig({
              ...config,
              correction_type: e.target.value as CorrectionType,
            })
          }
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
        <div className="mb-4 p-3 bg-gray-50 rounded">
          <p className="text-sm font-medium mb-2">Barrel Distortion Parameters</p>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-gray-600">
                k1 (Quadratic): {(config.correction_params as any).k1?.toFixed(2) || 0}
              </label>
              <input
                type="range"
                min="-1"
                max="1"
                step="0.01"
                value={(config.correction_params as any).k1 || 0}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    correction_params: {
                      ...config.correction_params,
                      k1: parseFloat(e.target.value),
                    },
                  })
                }
                className="w-full"
              />
            </div>
            <div>
              <label className="text-xs text-gray-600">
                k2 (Quartic): {(config.correction_params as any).k2?.toFixed(2) || 0}
              </label>
              <input
                type="range"
                min="-1"
                max="1"
                step="0.01"
                value={(config.correction_params as any).k2 || 0}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    correction_params: {
                      ...config.correction_params,
                      k2: parseFloat(e.target.value),
                    },
                  })
                }
                className="w-full"
              />
            </div>
          </div>
        </div>
      )}

      {config.correction_type === 'cylindrical' && (
        <div className="mb-4 p-3 bg-gray-50 rounded">
          <p className="text-sm font-medium mb-2">Cylindrical Parameters</p>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-gray-600">
                Radius: {(config.correction_params as any).radius?.toFixed(1) || 1.0}
              </label>
              <input
                type="range"
                min="0.1"
                max="5"
                step="0.1"
                value={(config.correction_params as any).radius || 1.0}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    correction_params: {
                      ...config.correction_params,
                      radius: parseFloat(e.target.value),
                    },
                  })
                }
                className="w-full"
              />
            </div>
            <div>
              <label className="text-xs text-gray-600">Axis</label>
              <select
                value={(config.correction_params as any).axis || 'horizontal'}
                onChange={(e) =>
                  setConfig({
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
        <div className="mb-4 p-3 bg-gray-50 rounded">
          <p className="text-sm font-medium mb-2">Equirectangular Parameters</p>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-gray-600">
                FOV Horizontal: {(config.correction_params as any).fov_h || 120}°
              </label>
              <input
                type="range"
                min="10"
                max="360"
                step="1"
                value={(config.correction_params as any).fov_h || 120}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    correction_params: {
                      ...config.correction_params,
                      fov_h: parseInt(e.target.value),
                    },
                  })
                }
                className="w-full"
              />
            </div>
            <div>
              <label className="text-xs text-gray-600">
                FOV Vertical: {(config.correction_params as any).fov_v || 90}°
              </label>
              <input
                type="range"
                min="10"
                max="180"
                step="1"
                value={(config.correction_params as any).fov_v || 90}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    correction_params: {
                      ...config.correction_params,
                      fov_v: parseInt(e.target.value),
                    },
                  })
                }
                className="w-full"
              />
            </div>
          </div>
        </div>
      )}

      {/* Presets */}
      <div className="mb-4 p-3 bg-blue-50 rounded">
        <p className="text-sm font-medium mb-2">Presets</p>
        <div className="flex gap-2 mb-2">
          <select
            value={selectedPreset}
            onChange={(e) => setSelectedPreset(e.target.value)}
            className="flex-1 px-2 py-1 border rounded text-sm"
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
            className="px-3 py-1 bg-blue-500 text-white rounded text-sm disabled:bg-gray-300"
          >
            Load
          </button>
          <button
            onClick={handlePresetDelete}
            disabled={!selectedPreset}
            className="px-3 py-1 bg-red-500 text-white rounded text-sm disabled:bg-gray-300"
          >
            Delete
          </button>
        </div>
        <button
          onClick={() => setShowPresetDialog(true)}
          className="w-full px-3 py-1 bg-green-500 text-white rounded text-sm"
        >
          Save Current as New Preset
        </button>
      </div>

      {/* Save Preset Dialog */}
      {showPresetDialog && (
        <div className="mb-4 p-3 bg-green-50 border border-green-300 rounded">
          <p className="text-sm font-medium mb-2">Save Preset</p>
          <input
            type="text"
            placeholder="Preset name"
            value={newPresetName}
            onChange={(e) => setNewPresetName(e.target.value)}
            className="w-full px-2 py-1 border rounded text-sm mb-2"
          />
          <input
            type="text"
            placeholder="Description (optional)"
            value={newPresetDesc}
            onChange={(e) => setNewPresetDesc(e.target.value)}
            className="w-full px-2 py-1 border rounded text-sm mb-2"
          />
          <div className="flex gap-2">
            <button
              onClick={handlePresetSave}
              className="flex-1 px-3 py-1 bg-green-600 text-white rounded text-sm"
            >
              Save
            </button>
            <button
              onClick={() => setShowPresetDialog(false)}
              className="flex-1 px-3 py-1 bg-gray-400 text-white rounded text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Apply Button */}
      <button
        onClick={handleApply}
        disabled={isApplying}
        className="w-full px-4 py-2 bg-blue-600 text-white rounded font-medium hover:bg-blue-700 disabled:bg-gray-400"
      >
        {isApplying ? 'Applying...' : 'Apply Configuration'}
      </button>
    </div>
  );
};
