/**
 * NVMM Buffer Manager Implementation
 *
 * Manages pool of NVMM (GPU) buffers for zero-copy operation
 * Allocates DMA-BUF handles for sharing between GStreamer elements
 */

#include "nvmm_buffer_manager.h"
#include <iostream>
#include <algorithm>
#include <cstring>

// In production: #include <nvbufsurface.h>
// Mock for compilation
#define NVBUF_MEM_SURFACE_ARRAY 1

namespace footballvision {

struct NVMMBufferManager::Impl {
    std::vector<NVMMBuffer*> buffer_pool;
    std::vector<bool> buffer_available;

    uint32_t total_buffers = 0;
    uint32_t used_buffers = 0;

    ~Impl() {
        Cleanup();
    }

    void Cleanup() {
        for (auto* buffer : buffer_pool) {
            if (buffer) {
                // In production: Free NVMM buffer
                // NvBufSurfaceDestroy((NvBufSurface*)buffer->dmabuf_fd);
                delete buffer;
            }
        }
        buffer_pool.clear();
        buffer_available.clear();
    }
};

std::unique_ptr<NVMMBufferManager> NVMMBufferManager::Create() {
    return std::make_unique<NVMMBufferManager>();
}

NVMMBufferManager::NVMMBufferManager()
    : impl_(std::make_unique<Impl>()) {
}

NVMMBufferManager::~NVMMBufferManager() {
    Cleanup();
}

bool NVMMBufferManager::Initialize(const BufferPoolConfig& config) {
    std::lock_guard<std::mutex> lock(mutex_);

    config_ = config;

    std::cout << "[NVMMBufferManager] Initializing buffer pool..." << std::endl;
    std::cout << "  Buffers: " << config.num_buffers << std::endl;
    std::cout << "  Size: " << config.buffer_size << " bytes each" << std::endl;
    std::cout << "  Resolution: " << config.width << "x" << config.height << std::endl;
    std::cout << "  Total memory: " << (config.num_buffers * config.buffer_size) / (1024*1024) << " MB" << std::endl;

    // Allocate buffer pool
    impl_->buffer_pool.resize(config.num_buffers);
    impl_->buffer_available.resize(config.num_buffers, true);

    for (uint32_t i = 0; i < config.num_buffers; i++) {
        // In production: Allocate NVMM buffer
        /*
        NvBufSurface* surf = nullptr;
        NvBufSurfaceAllocateParams params = {0};
        params.params.width = config.width;
        params.params.height = config.height;
        params.params.layout = NVBUF_LAYOUT_PITCH;
        params.params.colorFormat = NVBUF_COLOR_FORMAT_NV12;
        params.params.memType = NVBUF_MEM_SURFACE_ARRAY;
        params.memtag = NvBufSurfaceTag_CAMERA;

        if (NvBufSurfaceAllocate(&surf, 1, &params) != 0) {
            std::cerr << "Failed to allocate NVMM buffer " << i << std::endl;
            return false;
        }

        // Get DMA-BUF fd
        int dmabuf_fd = surf->surfaceList[0].bufferDesc;
        */

        // Mock allocation
        NVMMBuffer* buffer = new NVMMBuffer();
        buffer->dmabuf_fd = reinterpret_cast<void*>(static_cast<uintptr_t>(i + 1));  // Mock fd
        buffer->width = config.width;
        buffer->height = config.height;
        buffer->stride = config.width;  // Simplified
        buffer->size = config.buffer_size;
        buffer->timestamp_ns = 0;
        buffer->camera_id = -1;

        impl_->buffer_pool[i] = buffer;
        impl_->buffer_available[i] = true;

        std::cout << "  Allocated buffer " << i << std::endl;
    }

    impl_->total_buffers = config.num_buffers;
    impl_->used_buffers = 0;

    std::cout << "[NVMMBufferManager] Buffer pool initialized successfully" << std::endl;
    return true;
}

void NVMMBufferManager::Cleanup() {
    std::lock_guard<std::mutex> lock(mutex_);

    std::cout << "[NVMMBufferManager] Cleaning up buffer pool..." << std::endl;

    impl_->Cleanup();

    impl_->total_buffers = 0;
    impl_->used_buffers = 0;

    std::cout << "[NVMMBufferManager] Buffer pool cleaned up" << std::endl;
}

NVMMBuffer* NVMMBufferManager::AcquireBuffer() {
    std::lock_guard<std::mutex> lock(mutex_);

    // Find first available buffer
    for (uint32_t i = 0; i < impl_->total_buffers; i++) {
        if (impl_->buffer_available[i]) {
            impl_->buffer_available[i] = false;
            impl_->used_buffers++;

            NVMMBuffer* buffer = impl_->buffer_pool[i];
            buffer->timestamp_ns = 0;  // Reset timestamp

            return buffer;
        }
    }

    // No buffers available
    std::cerr << "[NVMMBufferManager] WARNING: No buffers available! Pool exhausted." << std::endl;
    return nullptr;
}

void NVMMBufferManager::ReleaseBuffer(NVMMBuffer* buffer) {
    if (!buffer) return;

    std::lock_guard<std::mutex> lock(mutex_);

    // Find buffer in pool
    for (uint32_t i = 0; i < impl_->total_buffers; i++) {
        if (impl_->buffer_pool[i] == buffer) {
            if (impl_->buffer_available[i]) {
                std::cerr << "[NVMMBufferManager] WARNING: Double release of buffer " << i << std::endl;
                return;
            }

            impl_->buffer_available[i] = true;
            impl_->used_buffers--;
            return;
        }
    }

    std::cerr << "[NVMMBufferManager] WARNING: Released buffer not found in pool" << std::endl;
}

uint32_t NVMMBufferManager::GetTotalBuffers() const {
    return impl_->total_buffers;
}

uint32_t NVMMBufferManager::GetAvailableBuffers() const {
    std::lock_guard<std::mutex> lock(mutex_);

    uint32_t available = 0;
    for (bool avail : impl_->buffer_available) {
        if (avail) available++;
    }
    return available;
}

uint32_t NVMMBufferManager::GetUsedBuffers() const {
    return impl_->used_buffers;
}

size_t NVMMBufferManager::GetTotalMemoryUsage() const {
    return static_cast<size_t>(config_.num_buffers) * config_.buffer_size;
}

bool NVMMBufferManager::IsHealthy() const {
    // Pool is healthy if we have at least 20% buffers available
    uint32_t available = GetAvailableBuffers();
    return available >= (impl_->total_buffers / 5);
}

bool NVMMBufferManager::HasAvailableBuffers() const {
    return GetAvailableBuffers() > 0;
}

} // namespace footballvision