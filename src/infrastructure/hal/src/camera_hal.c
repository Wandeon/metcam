/*
 * Camera Hardware Abstraction Layer
 * Unified interface for camera control
 */

#include <stdio.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/videodev2.h>

typedef struct {
    int fd;
    int width;
    int height;
    int fps;
} camera_t;

camera_t cameras[2] = {0};

int camera_init(int id, const char *device) {
    cameras[id].fd = open(device, O_RDWR);
    if (cameras[id].fd < 0) return -1;

    cameras[id].width = 4056;
    cameras[id].height = 3040;
    cameras[id].fps = 30;
    return 0;
}

int camera_set_exposure(int id, int us) {
    struct v4l2_control ctrl = {
        .id = V4L2_CID_EXPOSURE,
        .value = us
    };
    return ioctl(cameras[id].fd, VIDIOC_S_CTRL, &ctrl);
}

int camera_set_gain(int id, int gain) {
    struct v4l2_control ctrl = {
        .id = V4L2_CID_GAIN,
        .value = gain
    };
    return ioctl(cameras[id].fd, VIDIOC_S_CTRL, &ctrl);
}

void camera_close(int id) {
    if (cameras[id].fd >= 0) {
        close(cameras[id].fd);
        cameras[id].fd = -1;
    }
}