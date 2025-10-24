#!/usr/bin/env python3
"""
Shader Generator for Camera Distortion Correction
Generates GLSL fragment shaders for different correction types
"""

from typing import Dict, Any, List, Tuple
import math


def generate_barrel_shader(camera_id: int, k1: float, k2: float, rotation: float) -> str:
    """
    Generate barrel distortion correction shader

    Args:
        camera_id: Camera identifier (0 or 1)
        k1: Radial distortion coefficient (quadratic term)
        k2: Radial distortion coefficient (quartic term)
        rotation: Rotation angle in degrees

    Returns:
        GLSL fragment shader code
    """
    rotation_rad = math.radians(rotation)
    cos_theta = math.cos(rotation_rad)
    sin_theta = math.sin(rotation_rad)

    shader = f"""
#version 120
#ifdef GL_ES
precision mediump float;
#endif

varying vec2 v_texcoord;
uniform sampler2D tex;

void main() {{
    // Center coordinates
    vec2 center = vec2(0.5, 0.5);

    // Get texture coordinate relative to center
    vec2 pos = v_texcoord - center;

    // Apply rotation (camera {camera_id}: {rotation:+.1f}°)
    float cos_theta = {cos_theta:.10f};
    float sin_theta = {sin_theta:.10f};
    vec2 rotated = vec2(
        pos.x * cos_theta - pos.y * sin_theta,
        pos.x * sin_theta + pos.y * cos_theta
    );

    // Calculate radius from center
    float r = length(rotated);

    // Barrel distortion correction
    // r_undistorted = r * (1 + k1*r^2 + k2*r^4)
    float k1 = {k1:.10f};
    float k2 = {k2:.10f};
    float r2 = r * r;
    float r4 = r2 * r2;
    float distortion_factor = 1.0 + k1 * r2 + k2 * r4;

    // Apply distortion
    vec2 distorted = rotated * distortion_factor;

    // Convert back to texture coordinates
    vec2 final_coord = distorted + center;

    // Sample texture if within bounds, otherwise black
    if (final_coord.x >= 0.0 && final_coord.x <= 1.0 &&
        final_coord.y >= 0.0 && final_coord.y <= 1.0) {{
        gl_FragColor = texture2D(tex, final_coord);
    }} else {{
        gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
    }}
}}
"""
    return shader.strip()


def generate_cylindrical_shader(
    camera_id: int,
    radius: float,
    axis: str,
    rotation: float
) -> str:
    """
    Generate cylindrical projection correction shader

    Args:
        camera_id: Camera identifier (0 or 1)
        radius: Cylinder radius (affects curvature amount, typical: 0.5-2.0)
        axis: Cylinder axis ('horizontal' or 'vertical')
        rotation: Rotation angle in degrees

    Returns:
        GLSL fragment shader code
    """
    rotation_rad = math.radians(rotation)
    cos_theta = math.cos(rotation_rad)
    sin_theta = math.sin(rotation_rad)
    is_horizontal = axis.lower() == 'horizontal'

    shader = f"""
#version 120
#ifdef GL_ES
precision mediump float;
#endif

varying vec2 v_texcoord;
uniform sampler2D tex;

void main() {{
    // Center coordinates
    vec2 center = vec2(0.5, 0.5);

    // Get texture coordinate relative to center
    vec2 pos = v_texcoord - center;

    // Apply rotation (camera {camera_id}: {rotation:+.1f}°)
    float cos_theta = {cos_theta:.10f};
    float sin_theta = {sin_theta:.10f};
    vec2 rotated = vec2(
        pos.x * cos_theta - pos.y * sin_theta,
        pos.x * sin_theta + pos.y * cos_theta
    );

    // Cylindrical projection ({"horizontal" if is_horizontal else "vertical"} axis)
    float radius = {radius:.10f};
    vec2 corrected;

    {'// Horizontal cylinder - warp X axis' if is_horizontal else '// Vertical cylinder - warp Y axis'}
    {'''
    float theta = rotated.x / radius;
    corrected.x = sin(theta) * radius;
    corrected.y = rotated.y;
    ''' if is_horizontal else '''
    float theta = rotated.y / radius;
    corrected.x = rotated.x;
    corrected.y = sin(theta) * radius;
    '''}

    // Convert back to texture coordinates
    vec2 final_coord = corrected + center;

    // Sample texture if within bounds, otherwise black
    if (final_coord.x >= 0.0 && final_coord.x <= 1.0 &&
        final_coord.y >= 0.0 && final_coord.y <= 1.0) {{
        gl_FragColor = texture2D(tex, final_coord);
    }} else {{
        gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
    }}
}}
"""
    return shader.strip()


def generate_equirectangular_shader(
    camera_id: int,
    fov_h: float,
    fov_v: float,
    center_x: float,
    center_y: float,
    rotation: float
) -> str:
    """
    Generate equirectangular (spherical) projection correction shader

    Args:
        camera_id: Camera identifier (0 or 1)
        fov_h: Horizontal field of view in degrees (typical: 90-180)
        fov_v: Vertical field of view in degrees (typical: 60-120)
        center_x: Horizontal center offset (0.5 = centered, typical: 0.4-0.6)
        center_y: Vertical center offset (0.5 = centered, typical: 0.4-0.6)
        rotation: Rotation angle in degrees

    Returns:
        GLSL fragment shader code
    """
    rotation_rad = math.radians(rotation)
    cos_theta = math.cos(rotation_rad)
    sin_theta = math.sin(rotation_rad)
    fov_h_rad = math.radians(fov_h)
    fov_v_rad = math.radians(fov_v)

    shader = f"""
#version 120
#ifdef GL_ES
precision mediump float;
#endif

varying vec2 v_texcoord;
uniform sampler2D tex;

#define PI 3.14159265359

void main() {{
    // Center coordinates with offset
    vec2 center = vec2({center_x:.10f}, {center_y:.10f});

    // Get texture coordinate relative to center
    vec2 pos = v_texcoord - center;

    // Apply rotation (camera {camera_id}: {rotation:+.1f}°)
    float cos_theta = {cos_theta:.10f};
    float sin_theta = {sin_theta:.10f};
    vec2 rotated = vec2(
        pos.x * cos_theta - pos.y * sin_theta,
        pos.x * sin_theta + pos.y * cos_theta
    );

    // Equirectangular projection (spherical mapping)
    float fov_h = {fov_h_rad:.10f};  // {fov_h:.1f}°
    float fov_v = {fov_v_rad:.10f};  // {fov_v:.1f}°

    // Map to spherical coordinates
    float theta = rotated.x * fov_h;  // Horizontal angle
    float phi = rotated.y * fov_v;    // Vertical angle

    // Convert to 3D direction vector
    float cos_phi = cos(phi);
    vec3 dir = vec3(
        sin(theta) * cos_phi,
        sin(phi),
        cos(theta) * cos_phi
    );

    // Project back to plane (pinhole camera model)
    float scale = 1.0;
    if (abs(dir.z) > 0.001) {{
        scale = 1.0 / dir.z;
    }}

    vec2 corrected = vec2(dir.x * scale, dir.y * scale);

    // Convert back to texture coordinates
    vec2 final_coord = corrected + center;

    // Sample texture if within bounds, otherwise black
    if (final_coord.x >= 0.0 && final_coord.x <= 1.0 &&
        final_coord.y >= 0.0 && final_coord.y <= 1.0) {{
        gl_FragColor = texture2D(tex, final_coord);
    }} else {{
        gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
    }}
}}
"""
    return shader.strip()


def generate_perspective_shader(
    camera_id: int,
    corners: List[Tuple[float, float]],
    rotation: float
) -> str:
    """
    Generate perspective transform (keystone correction) shader

    Args:
        camera_id: Camera identifier (0 or 1)
        corners: List of 4 corner points [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
                 in normalized coordinates (0.0-1.0), order: top-left, top-right,
                 bottom-right, bottom-left
        rotation: Rotation angle in degrees

    Returns:
        GLSL fragment shader code
    """
    if len(corners) != 4:
        raise ValueError("Perspective transform requires exactly 4 corner points")

    rotation_rad = math.radians(rotation)
    cos_theta = math.cos(rotation_rad)
    sin_theta = math.sin(rotation_rad)

    # Calculate perspective transform matrix (homography)
    # Using bilinear interpolation approximation for GPU efficiency
    tl, tr, br, bl = corners

    shader = f"""
#version 120
#ifdef GL_ES
precision mediump float;
#endif

varying vec2 v_texcoord;
uniform sampler2D tex;

void main() {{
    // Center coordinates
    vec2 center = vec2(0.5, 0.5);

    // Get texture coordinate relative to center
    vec2 pos = v_texcoord - center;

    // Apply rotation (camera {camera_id}: {rotation:+.1f}°)
    float cos_theta = {cos_theta:.10f};
    float sin_theta = {sin_theta:.10f};
    vec2 rotated = vec2(
        pos.x * cos_theta - pos.y * sin_theta,
        pos.x * sin_theta + pos.y * cos_theta
    );

    // Convert back to [0,1] range for bilinear interpolation
    vec2 normalized = rotated + center;
    float u = normalized.x;
    float v = normalized.y;

    // Perspective transform using 4 corner points
    // Bilinear interpolation between corners
    vec2 tl = vec2({tl[0]:.10f}, {tl[1]:.10f});  // Top-left
    vec2 tr = vec2({tr[0]:.10f}, {tr[1]:.10f});  // Top-right
    vec2 br = vec2({br[0]:.10f}, {br[1]:.10f});  // Bottom-right
    vec2 bl = vec2({bl[0]:.10f}, {bl[1]:.10f});  // Bottom-left

    // Interpolate top edge
    vec2 top = mix(tl, tr, u);

    // Interpolate bottom edge
    vec2 bottom = mix(bl, br, u);

    // Interpolate between top and bottom
    vec2 corrected = mix(top, bottom, v);

    // Sample texture if within bounds, otherwise black
    if (corrected.x >= 0.0 && corrected.x <= 1.0 &&
        corrected.y >= 0.0 && corrected.y <= 1.0) {{
        gl_FragColor = texture2D(tex, corrected);
    }} else {{
        gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
    }}
}}
"""
    return shader.strip()


def get_shader_for_camera(camera_id: int, config: Dict[str, Any]) -> str:
    """
    Main entry point - generate shader based on camera configuration

    Args:
        camera_id: Camera identifier (0 or 1)
        config: Camera configuration dictionary with:
            - rotation: float (degrees)
            - correction_type: str ('barrel', 'cylindrical', 'equirectangular', 'perspective')
            - correction_params: dict (type-specific parameters)

    Returns:
        GLSL fragment shader code

    Raises:
        ValueError: If correction type is unknown
    """
    rotation = config.get('rotation', 0.0)
    correction_type = config.get('correction_type', 'barrel')
    params = config.get('correction_params', {})

    if correction_type == 'barrel':
        k1 = params.get('k1', 0.15)
        k2 = params.get('k2', 0.05)
        return generate_barrel_shader(camera_id, k1, k2, rotation)

    elif correction_type == 'cylindrical':
        radius = params.get('radius', 1.0)
        axis = params.get('axis', 'horizontal')
        return generate_cylindrical_shader(camera_id, radius, axis, rotation)

    elif correction_type == 'equirectangular':
        fov_h = params.get('fov_h', 120.0)
        fov_v = params.get('fov_v', 90.0)
        center_x = params.get('center_x', 0.5)
        center_y = params.get('center_y', 0.5)
        return generate_equirectangular_shader(
            camera_id, fov_h, fov_v, center_x, center_y, rotation
        )

    elif correction_type == 'perspective':
        # Default corners (no transform)
        default_corners = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        corners_list = params.get('corners', default_corners)
        corners = [tuple(c) if isinstance(c, list) else c for c in corners_list]
        return generate_perspective_shader(camera_id, corners, rotation)

    else:
        raise ValueError(f"Unknown correction type: {correction_type}")


def get_default_params(correction_type: str) -> Dict[str, Any]:
    """
    Get default parameters for a correction type

    Args:
        correction_type: Type of correction

    Returns:
        Dictionary of default parameters
    """
    defaults = {
        'barrel': {
            'k1': 0.15,
            'k2': 0.05
        },
        'cylindrical': {
            'radius': 1.0,
            'axis': 'horizontal'
        },
        'equirectangular': {
            'fov_h': 120.0,
            'fov_v': 90.0,
            'center_x': 0.5,
            'center_y': 0.5
        },
        'perspective': {
            'corners': [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        }
    }
    return defaults.get(correction_type, {})


if __name__ == "__main__":
    # Test shader generation
    print("=== Testing Shader Generator ===\n")

    # Test 1: Barrel correction
    print("1. Barrel Correction Shader (Camera 0, +18°, k1=0.15, k2=0.05)")
    barrel_config = {
        'rotation': 18.0,
        'correction_type': 'barrel',
        'correction_params': {'k1': 0.15, 'k2': 0.05}
    }
    shader = get_shader_for_camera(0, barrel_config)
    print(f"   Generated {len(shader)} bytes of GLSL code")
    print(f"   First line: {shader.split(chr(10))[0]}")

    # Test 2: Cylindrical correction
    print("\n2. Cylindrical Correction Shader (Camera 1, -18°, radius=1.2)")
    cyl_config = {
        'rotation': -18.0,
        'correction_type': 'cylindrical',
        'correction_params': {'radius': 1.2, 'axis': 'horizontal'}
    }
    shader = get_shader_for_camera(1, cyl_config)
    print(f"   Generated {len(shader)} bytes of GLSL code")

    # Test 3: Equirectangular correction
    print("\n3. Equirectangular Correction Shader (Camera 0, 0°, FOV 120×90)")
    equirect_config = {
        'rotation': 0.0,
        'correction_type': 'equirectangular',
        'correction_params': {'fov_h': 120.0, 'fov_v': 90.0, 'center_x': 0.5, 'center_y': 0.5}
    }
    shader = get_shader_for_camera(0, equirect_config)
    print(f"   Generated {len(shader)} bytes of GLSL code")

    # Test 4: Perspective correction
    print("\n4. Perspective Correction Shader (Camera 1, +10°, keystone)")
    persp_config = {
        'rotation': 10.0,
        'correction_type': 'perspective',
        'correction_params': {
            'corners': [(0.1, 0.0), (0.9, 0.0), (1.0, 1.0), (0.0, 1.0)]
        }
    }
    shader = get_shader_for_camera(1, persp_config)
    print(f"   Generated {len(shader)} bytes of GLSL code")

    # Test 5: Default parameters
    print("\n5. Default Parameters")
    for ctype in ['barrel', 'cylindrical', 'equirectangular', 'perspective']:
        defaults = get_default_params(ctype)
        print(f"   {ctype}: {defaults}")

    print("\n✅ All shader types generated successfully!")
