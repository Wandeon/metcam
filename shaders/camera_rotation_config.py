#!/usr/bin/env python3
"""
Camera Rotation Configuration

Edit these values to adjust rotation per camera.
Angles are in degrees.

Positive = counter-clockwise rotation
Negative = clockwise rotation
"""

# Camera rotation angles (in degrees)
CAMERA_ROTATIONS = {
    0: 18.0,   # Camera 0: 18° counter-clockwise
    1: -18.0,  # Camera 1: 18° clockwise
}

# Barrel distortion coefficients
# Adjust these based on your lens calibration
DISTORTION_K1 = 0.15  # Quadratic term
DISTORTION_K2 = 0.05  # Quartic term


def degrees_to_radians(degrees):
    """Convert degrees to radians"""
    import math
    return degrees * math.pi / 180.0


def generate_shader(camera_id):
    """Generate shader code for specific camera with its rotation"""
    angle_degrees = CAMERA_ROTATIONS.get(camera_id, 0.0)
    angle_radians = degrees_to_radians(angle_degrees)

    shader_code = f"""#version 100
#ifdef GL_ES
precision mediump float;
#endif

varying vec2 v_texcoord;
uniform sampler2D tex;

// Barrel distortion correction
const float k1 = {DISTORTION_K1};
const float k2 = {DISTORTION_K2};

// Camera {camera_id} rotation: {angle_degrees}° ({angle_radians:.6f} radians)
const float rotation_angle = {angle_radians:.6f};

void main() {{
    vec2 center = vec2(0.5, 0.5);
    vec2 coord = v_texcoord - center;

    // Rotate
    float cos_angle = cos(rotation_angle);
    float sin_angle = sin(rotation_angle);
    vec2 rotated = vec2(
        coord.x * cos_angle - coord.y * sin_angle,
        coord.x * sin_angle + coord.y * cos_angle
    );

    // Barrel correction
    float r2 = dot(rotated, rotated);
    float r4 = r2 * r2;
    float distortion = 1.0 + k1 * r2 + k2 * r4;

    vec2 distorted = center + rotated * distortion;

    // Sample with bounds check
    if (distorted.x < 0.0 || distorted.x > 1.0 ||
        distorted.y < 0.0 || distorted.y > 1.0) {{
        gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
    }} else {{
        gl_FragColor = texture2D(tex, distorted);
    }}
}}
"""
    return shader_code


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: camera_rotation_config.py <camera_id>")
        print()
        print("Current configuration:")
        for cam_id, angle in CAMERA_ROTATIONS.items():
            print(f"  Camera {cam_id}: {angle:+.1f}°")
        sys.exit(1)

    camera_id = int(sys.argv[1])
    print(generate_shader(camera_id))
