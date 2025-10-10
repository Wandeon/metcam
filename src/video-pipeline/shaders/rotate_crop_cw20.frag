uniform sampler2D video_texture;
varying vec2 v_texcoord;

const float COS_A = 0.9396926;
const float SIN_A = 0.3420201;
const float ZOOM_X = 0.65;
const float ZOOM_Y = 0.65;
const float ASPECT_RATIO = 16.0 / 9.0;

void main()
{
    vec2 centered = v_texcoord - vec2(0.5);
    centered.x *= ASPECT_RATIO;
    centered *= vec2(ZOOM_X, ZOOM_Y);
    mat2 rot = mat2(COS_A, SIN_A,
                   -SIN_A, COS_A);
    vec2 rotated = rot * centered;
    rotated.x /= ASPECT_RATIO;
    vec2 final_coord = rotated + vec2(0.5);

    if (final_coord.x < 0.0 || final_coord.x > 1.0 || final_coord.y < 0.0 || final_coord.y > 1.0) {
        gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
    } else {
        gl_FragColor = texture2D(video_texture, final_coord);
    }
}
