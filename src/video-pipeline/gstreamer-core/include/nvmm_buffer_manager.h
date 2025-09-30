/**
 * NVMM Buffer Manager
 * Zero-copy buffer pool management for GPU memory
 */

#ifndef FOOTBALLVISION_NVMM_BUFFER_MANAGER_H
#define FOOTBALLVISION_NVMM_BUFFER_MANAGER_H

#include "footballvision/interfaces.h"
#include <vector>
#include <memory>
#include <mutex>

namespace footballvision {

struct BufferPoolConfig {
    uint32_t num_buffers;
    uint32_t buffer_size;
    uint32_t width;
    uint32_t height;
    uint32_t memory_type;  // NVBUF_MEM_SURFACE_ARRAY
    uint32_t alignment;    // 256-byte aligned
};

class NVMMBufferManager {
public:
    static std::unique_ptr<NVMMBufferManager> Create();

    NVMMBufferManager();
    ~NVMMBufferManager();

    // Pool management
    bool Initialize(const BufferPoolConfig& config);
    void Cleanup();

    // Buffer allocation
    NVMMBuffer* AcquireBuffer();
    void ReleaseBuffer(NVMMBuffer* buffer);

    // Statistics
    uint32_t GetTotalBuffers() const;
    uint32_t GetAvailableBuffers() const;
    uint32_t GetUsedBuffers() const;
    size_t GetTotalMemoryUsage() const;

    // Health check
    bool IsHealthy() const;
    bool HasAvailableBuffers() const;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;

    BufferPoolConfig config_;
    mutable std::mutex mutex_;
};

} // namespace footballvision

#endif // FOOTBALLVISION_NVMM_BUFFER_MANAGER_H