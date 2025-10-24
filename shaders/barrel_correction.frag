#version 100
#ifdef GL_ES
precision mediump float;
#endif

varying vec2 v_texcoord;
uniform sampler2D tex;

// Barrel distortion correction parameters
// Positive values correct barrel distortion (pincushion effect)
// Start with mild correction and adjust based on your lens
const float k1 = 0.15;  // Quadratic distortion coefficient
const float k2 = 0.05;  // Quartic distortion coefficient

void main() {
    // Center coordinates (-1 to 1)
    vec2 center = vec2(0.5, 0.5);
    vec2 coord = v_texcoord - center;

    // Calculate radius from center
    float r2 = dot(coord, coord);
    float r4 = r2 * r2;

    // Apply barrel correction (inverse of fisheye)
    // This creates pincushion distortion to counteract barrel distortion
    float distortion = 1.0 + k1 * r2 + k2 * r4;

    // Apply distortion to coordinates
    vec2 distorted = center + coord * distortion;

    // Sample texture at distorted coordinates
    // Check bounds to avoid sampling outside texture
    if (distorted.x < 0.0 || distorted.x > 1.0 || distorted.y < 0.0 || distorted.y > 1.0) {
        gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);  // Black for out-of-bounds
    } else {
        gl_FragColor = texture2D(tex, distorted);
    }
}
