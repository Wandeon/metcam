# Camera Controls - Quick Reference Guide

## Quick Start (5 Minutes)

1. **Open Web Dashboard**
   - Navigate to http://vid.nk-otok.hr

2. **Go to Preview Tab**
   - Click "Preview" in the navigation

3. **Start Preview**
   - Click "Start Recording Preview"
   - Wait for streams to appear (~3 seconds)

4. **Show Camera Controls**
   - Click "Show Controls" button
   - Two control panels appear (Camera 0 and Camera 1)

5. **Adjust Settings**
   - Move rotation slider to tilt image
   - Change crop values to adjust field of view
   - Select correction type from dropdown
   - Adjust correction parameters

6. **Apply Changes**
   - Click "Apply Configuration" button
   - Preview automatically restarts (~5 seconds)
   - Changes are now visible

7. **Save as Preset (Optional)**
   - Click "Save Current as New Preset"
   - Enter name: e.g., "Match Day Setup"
   - Enter description: e.g., "Perfect alignment for home field"
   - Click "Save"

## Common Adjustments

### Fix Tilted Field
```
Problem: Field appears rotated
Solution:
  1. Adjust rotation slider
  2. Camera 0: Positive = counter-clockwise
  3. Camera 1: Negative = clockwise
  4. Click Apply
```

### Adjust Field Coverage
```
Problem: Too much/little field visible
Solution:
  1. Modify crop values
  2. Left/Right: Horizontal coverage
  3. Top/Bottom: Vertical coverage
  4. Increase crop = less field visible
  5. Decrease crop = more field visible
  6. Click Apply
```

### Fix Curved Lines (Barrel Distortion)
```
Problem: Straight lines appear curved
Solution:
  1. Select "Barrel" correction type
  2. Adjust k1 slider:
     - Increase if lines curve outward
     - Decrease if lines curve inward
  3. Fine-tune k2 for edges
  4. Click Apply
```

### Save Your Perfect Setup
```
When: You've found the perfect settings
Steps:
  1. Verify preview looks correct
  2. Click "Save Current as New Preset"
  3. Name it descriptively
  4. Add helpful description
  5. Click Save

Later: Select from dropdown and click Load
```

## Parameter Cheat Sheet

| Parameter | Range | Default | Common Use |
|-----------|-------|---------|------------|
| **Rotation** | -180° to +180° | 0° | Fix camera tilt |
| **Crop Left** | 0-1920 px | 480 | Remove left edge |
| **Crop Right** | 0-1920 px | 480 | Remove right edge |
| **Crop Top** | 0-1080 px | 272 | Remove top edge |
| **Crop Bottom** | 0-1080 px | 272 | Remove bottom edge |
| **k1 (Barrel)** | -1.0 to +1.0 | 0.00 | Main distortion |
| **k2 (Barrel)** | -1.0 to +1.0 | 0.00 | Edge distortion |

## Correction Types at a Glance

### Barrel Correction ⭐ (Most Common)
- **Use**: Standard camera lens distortion
- **Parameters**: k1, k2
- **When**: Straight lines appear curved
- **Tip**: Adjust k1 first, then k2

### Cylindrical Projection
- **Use**: Panoramic or ultra-wide cameras
- **Parameters**: Radius, Axis (H/V)
- **When**: Very wide field of view (>120°)
- **Tip**: Start with radius = 1.0

### Equirectangular (Spherical)
- **Use**: Fisheye lenses, 360° cameras
- **Parameters**: FOV H/V, Center X/Y
- **When**: Extreme distortion, >180° FOV
- **Tip**: Match FOV to lens specs

### Perspective Transform
- **Use**: Manual keystone correction
- **Parameters**: 4 corner points
- **When**: Camera angle creates trapezoid
- **Tip**: Adjust one corner at a time

## Workflow Tips

### Before a Match
1. Load your preset for this field
2. Start preview to verify
3. Make minor adjustments if needed
4. Apply and check again
5. Stop preview
6. Start recording when ready

### Testing New Settings
1. Start preview first
2. Make ONE change at a time
3. Click Apply after each change
4. Verify result before next change
5. Save successful configuration as preset
6. Name it descriptively for future use

### Camera Swap/Replacement
1. Start the preview stream
2. Adjust rotation to level horizon
3. Adjust crop to frame field
4. Select correction type
5. Fine-tune parameters
6. Apply and verify
7. Save as "after_cam_swap" preset

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Apply button does nothing | Preview must be running first - click "Start Recording Preview" |
| Settings don't change | Click "Apply Configuration" to restart preview |
| Preview shows black screen | Stop and start preview again |
| Preset doesn't load | Check if preview is running, it will auto-restart |
| Changes lost after reboot | Click "Apply" before stopping - changes auto-save |
| Rotation creates black corners | Use crop to remove black areas |

## Keyboard Shortcuts

None currently - use mouse/touch interface.

## Best Practices

### ✅ DO:
- Start preview before making changes
- Make small adjustments (0.1° rotation, 10px crop)
- Save working configurations as presets
- Name presets descriptively
- Test changes before recording important matches
- Use the live preview to confirm focus and framing

### ❌ DON'T:
- Make multiple large changes at once
- Delete the "default" preset (system prevents this)
- Apply changes while recording (system prevents this)
- Make changes without preview running (no visual feedback)

## API Access (Advanced)

For automation or scripting:

```bash
# Get current config
curl http://localhost:8000/api/v1/camera/config/0

# Update rotation
curl -X POST http://localhost:8000/api/v1/camera/config/0 \
  -H "Content-Type: application/json" \
  -d '{"rotation": 19.0}'

# Load preset
curl -X POST http://localhost:8000/api/v1/camera/presets/default/load

# Apply changes
curl -X POST http://localhost:8000/api/v1/camera/apply
```

## Configuration File

Direct editing (advanced users):
```bash
# Location
/home/mislav/footballvision-pro/config/camera_config.json

# Edit manually
nano /home/mislav/footballvision-pro/config/camera_config.json

# Restart API to apply
sudo systemctl restart footballvision-api-enhanced
```

## Getting Help

1. Check full documentation: `docs/CAMERA_CONFIGURATION.md`
2. Review API logs: `tail -f /var/log/footballvision/api/api_v3.log`
3. Test API directly: `curl http://localhost:8000/api/v1/camera/config`
4. Verify preview service: `curl http://localhost:8000/api/v1/preview/status`

## Quick Reference Values

### Current Production Settings

**Camera 0** (Left):
- Rotation: 0.0°
- Crop: L=480, R=480, T=272, B=272
- Type: Barrel
- k1=0.00, k2=0.00

**Camera 1** (Right):
- Rotation: 0.0°
- Crop: L=480, R=480, T=272, B=272
- Type: Barrel
- k1=0.00, k2=0.00

**Output**: 2880×1616 @ 30fps

### Backup Default Settings

If you need to reset to factory defaults, use these values above or load the "default" preset.

---

**Last Updated**: 2025-10-20
**Version**: 1.1
