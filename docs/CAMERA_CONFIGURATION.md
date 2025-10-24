# Camera Configuration System

## Overview

The FootballVision Pro camera configuration system provides interactive controls for adjusting camera settings, distortion correction, and presets through the web interface. All settings are persistent and survive system restarts.

## Configuration File

Camera configurations are stored in:
```
/home/mislav/footballvision-pro/config/camera_config.json
```

## Accessing Controls

1. Open the Preview tab in the web dashboard
2. Click "Show Controls" in the Camera Configuration section
3. Adjust settings for each camera independently
4. Click "Apply Configuration" to restart the preview stream with new settings

## Configuration Parameters

### 1. Rotation

**Purpose**: Rotate the camera image to correct for camera mounting angle

**Range**: -180° to +180°
- **Positive values**: Counter-clockwise rotation
- **Negative values**: Clockwise rotation
- **Step**: 0.1° for fine adjustment

**Current Settings**:
- Camera 0: 0.0°
- Camera 1: 0.0°

**Use Cases**:
- Correcting for camera tilt during installation
- Fine-tuning field alignment
- Compensating for mounting bracket angle

### 2. Crop

**Purpose**: Remove unwanted portions of the image and define the field of view

**Parameters**:
- **Left**: Pixels to crop from left edge (0-1920)
- **Right**: Pixels to crop from right edge (0-1920)
- **Top**: Pixels to crop from top edge (0-1080)
- **Bottom**: Pixels to crop from bottom edge (0-1080)

**How Crop Works**:
- Crop values are **trim amounts**, not edge coordinates
- Final width = 3840 - left - right
- Final height = 2160 - top - bottom
- For 2880×1616 output: remove 960 horizontal pixels and 544 vertical pixels in total

**Current Settings**:
- **Camera 0**: left=480, right=480, top=272, bottom=272
- **Camera 1**: left=480, right=480, top=272, bottom=272

**Use Cases**:
- Removing black edges from rotation
- Adjusting field of view
- Centering the field in the frame
- Compensating for camera position offset

### 3. Distortion Correction Types

The system supports four different distortion correction algorithms. Each has specific use cases and parameters.

---

#### 3.1 Barrel Correction (Radial Distortion)

**Purpose**: Correct for lens barrel/pincushion distortion

**When to Use**:
- Wide-angle lenses with curved edges
- Standard camera lenses with geometric distortion
- Most common correction type for sports cameras

**Parameters**:

##### k1 (Quadratic Coefficient)
- **Range**: -1.0 to +1.0
- **Default**: 0.00
- **Step**: 0.01
- **Effect**:
  - Positive values: Corrects barrel distortion (curved outward)
  - Negative values: Corrects pincushion distortion (curved inward)
  - Magnitude controls strength of correction

##### k2 (Quartic Coefficient)
- **Range**: -1.0 to +1.0
- **Default**: 0.00
- **Step**: 0.01
- **Effect**:
  - Higher-order correction for severe distortion
  - Usually smaller than k1
  - Fine-tunes edge distortion

**Mathematical Model**:
```
r_distorted = r * (1 + k1*r² + k2*r⁴)
```

**Tuning Tips**:
1. Start with k1, adjust until center looks correct
2. Fine-tune edges with k2
3. Typical values: k1 = 0.1-0.2, k2 = 0.0-0.1
4. Use calibration images (checkerboard) for precision

---

#### 3.2 Cylindrical Projection

**Purpose**: Map a cylindrical surface to a flat plane

**When to Use**:
- Panoramic camera views
- Ultra-wide-angle lenses (>120° FOV)
- Cylindrical lens distortion patterns
- Creating virtual cylindrical wrapping effect

**Parameters**:

##### Radius
- **Range**: 0.1 to 5.0
- **Default**: 1.0
- **Step**: 0.1
- **Effect**:
  - Larger values: Less curvature (flatter projection)
  - Smaller values: More curvature (tighter cylinder)
  - 1.0 = standard cylindrical mapping

##### Axis
- **Options**: Horizontal, Vertical
- **Default**: Horizontal
- **Effect**:
  - Horizontal: Warps along X-axis (left-right panorama)
  - Vertical: Warps along Y-axis (top-bottom)

**Use Cases**:
- 180° panoramic field views
- Correcting cylindrical lens artifacts
- Creating "unwrapped" views from cylindrical cameras

**Tuning Tips**:
1. Start with radius = 1.0, horizontal axis
2. Increase radius if image appears too compressed
3. Decrease radius if edges appear too stretched
4. Switch axis if distortion is in wrong direction

---

#### 3.3 Equirectangular Projection (Spherical)

**Purpose**: Map spherical coordinates to rectangular image

**When to Use**:
- 360° cameras or very wide FOV
- Fisheye lenses (>180° FOV)
- Spherical panoramic corrections
- Creating flat views from hemispherical captures

**Parameters**:

##### FOV Horizontal
- **Range**: 10° to 360°
- **Default**: 120°
- **Step**: 1°
- **Effect**: Horizontal field of view angle
  - 90° = Normal wide-angle
  - 120° = Wide wide-angle
  - 180° = Hemispherical (fisheye)
  - 360° = Full panoramic wrap

##### FOV Vertical
- **Range**: 10° to 180°
- **Default**: 90°
- **Step**: 1°
- **Effect**: Vertical field of view angle
  - 60° = Standard view
  - 90° = Tall view
  - 120° = Very tall view
  - 180° = Full hemisphere vertical

##### Center X
- **Range**: 0.0 to 1.0
- **Default**: 0.5
- **Step**: 0.01
- **Effect**: Horizontal center point (0.5 = centered)
  - <0.5: Shift projection left
  - >0.5: Shift projection right

##### Center Y
- **Range**: 0.0 to 1.0
- **Default**: 0.5
- **Step**: 0.01
- **Effect**: Vertical center point (0.5 = centered)
  - <0.5: Shift projection up
  - >0.5: Shift projection down

**Mathematical Model**:
```
θ = (x - center_x) * fov_h
φ = (y - center_y) * fov_v
direction = (sin(θ)cos(φ), sin(φ), cos(θ)cos(φ))
```

**Use Cases**:
- Fisheye lens correction
- 360° camera footage
- Dome camera unwrapping
- VR/AR content preparation

**Tuning Tips**:
1. Match FOV_H and FOV_V to lens specifications
2. Adjust center_x/y to align optical center
3. For fisheye: Start with FOV_H=180°, FOV_V=180°
4. For wide-angle: Start with FOV_H=120°, FOV_V=90°

---

#### 3.4 Perspective Transform (Keystone Correction)

**Purpose**: Correct for perspective distortion and keystone effects

**When to Use**:
- Camera not perpendicular to field
- Trapezoidal distortion (keystoning)
- Manual geometric correction
- Aligning tilted views

**Parameters**:

##### Corners (4 points)
- **Format**: [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
- **Range**: 0.0 to 1.0 (normalized coordinates)
- **Default**: [(0,0), (1,0), (1,1), (0,1)] (no transform)
- **Order**: Top-left, Top-right, Bottom-right, Bottom-left

**Each Corner**:
- **X coordinate**: 0.0 = left edge, 1.0 = right edge
- **Y coordinate**: 0.0 = top edge, 1.0 = bottom edge

**Example Corrections**:

**Keystone (camera looking up)**:
```json
{
  "corners": [
    [0.1, 0.0],  // Top-left moved right
    [0.9, 0.0],  // Top-right moved left
    [1.0, 1.0],  // Bottom-right unchanged
    [0.0, 1.0]   // Bottom-left unchanged
  ]
}
```

**Rotation correction**:
```json
{
  "corners": [
    [0.05, 0.05],  // Slight inward adjustment
    [0.95, 0.0],   // Top-right
    [1.0, 0.95],   // Bottom-right
    [0.0, 1.0]     // Bottom-left
  ]
}
```

**Use Cases**:
- Correcting vertical keystoning
- Manual perspective alignment
- Compensating for angled camera placement
- Fine-tuning after automated corrections

**Tuning Tips**:
1. Identify which corners need adjustment
2. Make small changes (0.05-0.1) at a time
3. Adjust opposite corners together for symmetry
4. Use reference grid/field lines for alignment
5. Start with default and modify one corner at a time

---

## Preset System

### What are Presets?

Presets save complete camera configurations (both cameras, all parameters) as named snapshots.

### Using Presets

**Save Current Configuration**:
1. Adjust cameras to desired settings
2. Click "Save Current as New Preset"
3. Enter preset name and description
4. Click "Save"

**Load Preset**:
1. Select preset from dropdown
2. Click "Load"
3. Configuration applies immediately
4. If preview is running, it restarts automatically

**Delete Preset**:
1. Select preset from dropdown
2. Click "Delete"
3. Confirm deletion
4. Note: "default" preset cannot be deleted

### Preset Storage

Presets are stored in the same `camera_config.json` file:
```json
{
  "version": "1.0",
  "cameras": { ... },
  "presets": {
    "default": {
      "name": "Default Settings",
      "description": "Standard match recording setup",
      "cameras": { ... }
    },
    "tight_crop": {
      "name": "Tight Crop",
      "description": "Closer view for penalty area",
      "cameras": { ... }
    }
  }
}
```

### Preset Use Cases

- **Match Configurations**: Different crops for different field sizes
- **Weather Conditions**: Adjusted settings for different lighting
- **Camera Positions**: Multiple mounting locations/angles
- **Testing**: Quick switching between experimental settings
- **Backup**: Save working configuration before experimenting

---

## API Endpoints

### Camera Configuration

```bash
# Get all camera configs
GET /api/v1/camera/config

# Get specific camera config
GET /api/v1/camera/config/{cam_id}

# Update camera config
POST /api/v1/camera/config/{cam_id}
{
  "rotation": 18.5,
  "crop": {
    "left": 557,
    "right": 403,
    "top": 227,
    "bottom": 313
  },
  "correction_type": "barrel",
  "correction_params": {
    "k1": 0.15,
    "k2": 0.05
  }
}

# Apply configuration (restart preview)
POST /api/v1/camera/apply
```

### Presets

```bash
# List all presets
GET /api/v1/camera/presets

# Get specific preset
GET /api/v1/camera/presets/{name}

# Save current config as preset
POST /api/v1/camera/presets/{name}
{
  "description": "My custom configuration"
}

# Load preset
POST /api/v1/camera/presets/{name}/load

# Delete preset
DELETE /api/v1/camera/presets/{name}
```

---

## Workflow Examples

### Example 1: Adjusting Field Alignment

**Problem**: Field appears tilted in recording

**Solution**:
1. Open Preview tab, start preview
2. Show camera controls
3. Adjust Camera 0 rotation slider
4. Click "Apply Configuration"
5. Preview restarts with new rotation
6. Fine-tune until field is level
7. Optionally save as preset "field_level"

### Example 2: Correcting Barrel Distortion

**Problem**: Wide-angle lens makes field edges curved

**Solution**:
1. Show camera controls
2. Ensure "Barrel" correction type selected
3. Adjust k1 slider while watching preview
4. Increase k1 if lines curve outward
5. Decrease k1 if lines curve inward
6. Fine-tune k2 for edge correction
7. Apply and verify with grid overlay

### Example 3: Different Fields, Different Crops

**Problem**: Recording at multiple field sizes

**Solution**:
1. Configure cameras for Field A (large field)
   - Wider crop to capture full field
2. Save as preset "field_a_wide"
3. Adjust crop for Field B (smaller field)
   - Tighter crop for closer view
4. Save as preset "field_b_tight"
5. Before each match, load appropriate preset

### Example 4: Seasonal Adjustments

**Problem**: Summer sun requires different settings than winter

**Solution**:
1. Configure for summer conditions
   - Might need less crop due to better visibility
   - Different rotation due to sun angle
2. Save as "summer_config"
3. Configure for winter conditions
   - Tighter crop for focus
   - Adjusted rotation
4. Save as "winter_config"
5. Switch seasonally

---

## Technical Details

### Pipeline Order

Camera processing happens in this order:
1. **Capture**: 4K image from sensor (3840×2160)
2. **Convert to RGBA**: For GPU processing
3. **Distortion Correction**: Apply selected correction type with rotation
4. **Crop**: Software crop to final FOV
5. **Encode**: Convert to H.264 stream

### Shader Implementation

Distortion corrections use OpenGL fragment shaders (GLSL) for GPU acceleration. Shaders are generated dynamically based on configuration in `/shaders/shader_generator.py`.

### Performance Impact

- **Barrel correction**: Minimal (~1% CPU)
- **Cylindrical**: Minimal (~1% CPU)
- **Equirectangular**: Low (~2% CPU)
- **Perspective**: Minimal (~1% CPU)
- **Rotation**: Minimal (part of shader)

All corrections run on GPU, so CPU impact is negligible.

### Configuration Persistence

- Changes saved immediately to disk
- Survives system restarts
- Atomic writes prevent corruption
- Thread-safe with reentrant locking

### Preview vs Recording

- Preview uses SAME pipeline as recording
- Preview: 3 Mbps bitrate
- Recording: 12 Mbps bitrate
- Same resolution, same FOV, same corrections
- "What you see is what you record"

---

## Troubleshooting

### Preview doesn't restart after clicking Apply

**Issue**: Preview was not running when Apply was clicked

**Solution**: Start preview first, then Apply will restart it with new settings

### Changes don't appear

**Issue**: Preview needs restart to show changes

**Solution**: Click "Apply Configuration" to restart preview

### Preset doesn't restore settings

**Issue**: Preset saves configuration at the moment of save

**Solution**: Ensure desired settings are active BEFORE saving preset

### Rotation creates black corners

**Issue**: This is expected behavior - rotation exposes areas outside sensor

**Solution**: Use crop parameters to remove black corners

### Apply hangs/freezes

**Issue**: API service has deadlock (fixed in v1.1)

**Solution**: Restart API service: `sudo systemctl restart footballvision-api-enhanced`

### Config changes lost after restart

**Issue**: Config file not writable or corrupted

**Solution**:
1. Check file permissions: `ls -la /home/mislav/footballvision-pro/config/`
2. Validate JSON: `python3 -m json.tool < camera_config.json`
3. Restore from backup if needed

---

## Advanced Topics

### Custom Correction Types

To add new correction algorithms:

1. Edit `/shaders/shader_generator.py`
2. Add new function `generate_custom_shader()`
3. Update `get_shader_for_camera()` switch statement
4. Add TypeScript type in `/src/types/camera.ts`
5. Update UI in `/src/components/CameraControlPanel.tsx`

### Calibration

For precise distortion correction:

1. Record calibration checkerboard pattern
2. Use OpenCV camera calibration tools
3. Extract distortion coefficients (k1, k2, etc.)
4. Input values into barrel correction parameters

### Batch Configuration

To configure multiple systems identically:

1. Configure one system perfectly
2. Copy `/config/camera_config.json` to other systems
3. Adjust camera-specific values if needed (rotation, crop)
4. Reload API service

### Integration with Recording

Configuration applies to both preview AND recording automatically. When recording starts, it uses the current configuration from `camera_config.json`.

---

## Support

For issues or questions:
- Check logs: `/var/log/footballvision/api/api_v3.log`
- Test API directly: `curl http://localhost:8000/api/v1/camera/config`
- Verify config file: `cat /home/mislav/footballvision-pro/config/camera_config.json`

---

## Version History

- **v1.1** (2025-10-20):
  - Added 4 correction types
  - Added preset system
  - Fixed threading deadlock
  - Interactive web UI
  - Persistent configuration

- **v1.0** (2025-10-15):
  - Hardcoded barrel correction
  - Static rotation values
  - Manual JSON editing only
