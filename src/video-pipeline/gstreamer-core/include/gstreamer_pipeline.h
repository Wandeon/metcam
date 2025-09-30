/**
 * GStreamer Pipeline Core
 * Main recording pipeline implementation
 */

#ifndef FOOTBALLVISION_GSTREAMER_PIPELINE_H
#define FOOTBALLVISION_GSTREAMER_PIPELINE_H

#include "footballvision/interfaces.h"
#include <memory>
#include <atomic>
#include <mutex>
#include <functional>
#include <string>

// Forward declare GStreamer types
typedef struct _GstElement GstElement;
typedef struct _GstBus GstBus;
typedef struct _GstMessage GstMessage;
typedef struct _GstBuffer GstBuffer;

namespace footballvision {

struct PipelineConfig {
    int camera_id;
    std::string output_path;

    // Camera settings
    uint32_t width = 4056;
    uint32_t height = 3040;
    uint32_t framerate = 30;

    // Buffer settings
    uint32_t queue_size = 30;
    uint32_t post_encode_queue_size = 100;

    // NVMM settings
    bool use_nvmm = true;
    uint32_t nvmm_buffers = 30;
};

class GStreamerPipeline : public IGStreamerPipeline {
public:
    static std::unique_ptr<GStreamerPipeline> Create();

    GStreamerPipeline();
    ~GStreamerPipeline() override;

    // IGStreamerPipeline implementation
    bool Initialize(int camera_id, const std::string& output_path) override;
    bool Start() override;
    bool Stop() override;
    bool Pause() override;
    bool Resume() override;

    PipelineState GetState() const override;
    bool IsHealthy() const override;

    NVMMBuffer* GetCurrentBuffer() override;
    void ReleaseBuffer(NVMMBuffer* buffer) override;

    bool SendEOS() override;
    bool FlushBuffers() override;

    // Extended API
    bool InitializeWithConfig(const PipelineConfig& config);
    void SetErrorCallback(std::function<void(const std::string&)> callback);
    void SetEOSCallback(std::function<void()> callback);

    // Statistics
    uint64_t GetFrameCount() const;
    uint64_t GetDroppedFrames() const;
    double GetCurrentFPS() const;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;

    PipelineConfig config_;
    std::atomic<PipelineState> state_;
    mutable std::mutex mutex_;

    // Internal methods
    bool BuildPipeline();
    void CleanupPipeline();
    bool SetPipelineState(int gst_state);
    void HandleBusMessage(GstMessage* message);
    static void OnPadAdded(GstElement* element, void* pad, void* user_data);
};

} // namespace footballvision

#endif // FOOTBALLVISION_GSTREAMER_PIPELINE_H