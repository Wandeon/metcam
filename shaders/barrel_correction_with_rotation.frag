#version 100
#ifdef GL_ES
precision mediump float;
#endif

varying vec2 v_texcoord;
uniform sampler2D tex;

// Barrel distortion correction parameters
const float k1 = 0.15;  // Quadratic distortion coefficient
const float k2 = 0.05;  // Quartic distortion coefficient

// Rotation angle in radians (16 degrees = 0.279 radians)
// Positive = counter-clockwise, Negative = clockwise
const float rotation_angle = 0.279;  // 16 degrees

void main() {
    // Center coordinates (-0.5 to 0.5)
    vec2 center = vec2(0.5, 0.5);
    vec2 coord = v_texcoord - center;

    // Apply rotation FIRST (before distortion correction)
    float cos_angle = cos(rotation_angle);
    float sin_angle = sin(rotation_angle);
    vec2 rotated = vec2(
        coord.x * cos_angle - coord.y * sin_angle,
        coord.x * sin_angle + coord.y * cos_angle
    );

    // Calculate radius from center (after rotation)
    float r2 = dot(rotated, rotated);
    float r4 = r2 * r2;

    // Apply barrel correction
    float distortion = 1.0 + k1 * r2 + k2 * r4;

    // Apply distortion to rotated coordinates
    vec2 distorted = center + rotated * distortion;

    // Sample texture at corrected position
    // Check bounds to avoid sampling outside texture
    if (distorted.x < 0.0 || distorted.x > 1.0 || distorted.y < 0.0 || distorted.y > 1.0) {
        gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);  // Black for out-of-bounds
    } else {
        gl_FragColor = texture2D(tex, distorted);
    }
}
