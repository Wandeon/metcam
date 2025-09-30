/*
 * NVMM Buffer Allocator
 * Zero-copy video buffer management using NVIDIA Multimedia API
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "nvbuf_utils.h"

#define NUM_BUFFERS 6
#define BUFFER_WIDTH 4056
#define BUFFER_HEIGHT 3040

typedef struct {
    int dmabuf_fd;
    void *data;
    size_t size;
    int in_use;
} nvmm_buffer_t;

static nvmm_buffer_t buffers[NUM_BUFFERS];

int nvmm_init(void) {
    NvBufSurfaceCreateParams params = {0};
    params.gpuId = 0;
    params.width = BUFFER_WIDTH;
    params.height = BUFFER_HEIGHT;
    params.size = 0;
    params.colorFormat = NVBUF_COLOR_FORMAT_NV12;
    params.layout = NVBUF_LAYOUT_PITCH;
    params.memType = NVBUF_MEM_SURFACE_ARRAY;

    for (int i = 0; i < NUM_BUFFERS; i++) {
        if (NvBufSurfaceCreate(&params, i, &buffers[i].dmabuf_fd) != 0) {
            return -1;
        }
        buffers[i].in_use = 0;
    }

    return 0;
}

int nvmm_alloc_buffer(void) {
    for (int i = 0; i < NUM_BUFFERS; i++) {
        if (!buffers[i].in_use) {
            buffers[i].in_use = 1;
            return i;
        }
    }
    return -1;
}

void nvmm_free_buffer(int id) {
    if (id >= 0 && id < NUM_BUFFERS) {
        buffers[id].in_use = 0;
    }
}

void nvmm_cleanup(void) {
    for (int i = 0; i < NUM_BUFFERS; i++) {
        if (buffers[i].dmabuf_fd >= 0) {
            NvBufSurfaceDestroy(buffers[i].dmabuf_fd);
        }
    }
}