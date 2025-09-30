/**
 * FootballVision Pro - Component Interfaces
 * Master interface definitions for all pipeline components
 */

#ifndef FOOTBALLVISION_INTERFACES_H
#define FOOTBALLVISION_INTERFACES_H

#include <cstdint>
#include <string>
#include <functional>
#include <memory>
#include <vector>

namespace footballvision {

// ============================================================================
// Common Types
// ============================================================================

enum class PipelineState {
    IDLE,
    STARTING,
    RECORDING,
    STOPPING,
    FINALIZING,
    ERROR,
    RECOVERY
};

struct NVMMBuffer {
    void* dmabuf_fd;
    uint64_t timestamp_ns;
    uint32_t width;
    uint32_t height;
    uint32_t stride;
    uint32_t size;
    int camera_id;
};

struct RecordingStatus {
    PipelineState state;
    uint64_t frames_recorded[2];
    uint64_t frames_dropped[2];
    uint64_t bytes_written[2];
    uint64_t duration_ns;
    double cpu_usage;
    uint64_t memory_usage;
};

struct PipelineMetrics {
    // Per-camera metrics
    struct CameraMetrics {
        uint64_t frames_captured;
        uint64_t frames_dropped;
        uint64_t frames_encoded;
        double current_fps;
        double average_fps;
        uint64_t encoding_latency_ns;
    } cameras[2];

    // System metrics
    double cpu_usage_percent;
    uint64_t memory_used_bytes;
    uint64_t disk_write_rate_bps;

    // Sync metrics
    int64_t timestamp_drift_ns;
    uint32_t sync_corrections;
};

struct RecordingResult {
    bool success;
    std::string camera0_path;
    std::string camera1_path;
    uint64_t duration_ns;
    uint64_t total_frames[2];
    std::string error_message;
};

struct CameraConfig {
    int sensor_id;
    uint32_t width;
    uint32_t height;
    uint32_t framerate;
    uint32_t exposure_time_us;
    double gain;
    int white_balance_mode;
    bool auto_exposure;
};

// ============================================================================
// W12: Camera Control Interface
// ============================================================================

class ICameraControl {
public:
    virtual ~ICameraControl() = default;

    virtual bool Initialize(const CameraConfig& config) = 0;
    virtual bool Start() = 0;
    virtual bool Stop() = 0;

    virtual bool SetExposure(uint32_t exposure_us) = 0;
    virtual bool SetGain(double gain) = 0;
    virtual bool SetWhiteBalance(int mode) = 0;
    virtual bool EnableAutoExposure(bool enable) = 0;

    virtual uint32_t GetExposure() const = 0;
    virtual double GetGain() const = 0;
    virtual bool IsRunning() const = 0;
};

// ============================================================================
// W13: GStreamer Core Interface
// ============================================================================

class IGStreamerPipeline {
public:
    virtual ~IGStreamerPipeline() = default;

    virtual bool Initialize(int camera_id, const std::string& output_path) = 0;
    virtual bool Start() = 0;
    virtual bool Stop() = 0;
    virtual bool Pause() = 0;
    virtual bool Resume() = 0;

    virtual PipelineState GetState() const = 0;
    virtual bool IsHealthy() const = 0;

    // Buffer management
    virtual NVMMBuffer* GetCurrentBuffer() = 0;
    virtual void ReleaseBuffer(NVMMBuffer* buffer) = 0;

    // Pipeline control
    virtual bool SendEOS() = 0;
    virtual bool FlushBuffers() = 0;
};

// ============================================================================
// W14: NVENC Interface
// ============================================================================

struct EncoderConfig {
    uint32_t bitrate_bps;
    uint32_t peak_bitrate_bps;
    uint32_t iframe_interval;
    int profile;  // 0=Baseline, 1=Main, 2=High
    int preset;   // 0=UltraFast, 1=Fast, 2=Medium
    bool insert_sps_pps;
    bool insert_vui;
};

class INVENCEncoder {
public:
    virtual ~INVENCEncoder() = default;

    virtual bool Initialize(const EncoderConfig& config) = 0;
    virtual bool Configure(const EncoderConfig& config) = 0;

    virtual bool EncodeFrame(const NVMMBuffer& input, void* output, size_t* output_size) = 0;
    virtual bool Flush() = 0;

    virtual uint64_t GetEncodedFrames() const = 0;
    virtual double GetAverageBitrate() const = 0;
};

// ============================================================================
// W15: Recording Manager Interface
// ============================================================================

class IRecordingManager {
public:
    virtual ~IRecordingManager() = default;

    virtual bool StartRecording(const std::string& game_id, const std::string& output_dir) = 0;
    virtual RecordingResult StopRecording() = 0;

    virtual RecordingStatus GetStatus() const = 0;
    virtual PipelineMetrics GetMetrics() const = 0;

    virtual bool IsRecording() const = 0;
    virtual uint64_t GetRecordingDuration() const = 0;

    // Metadata
    virtual bool SetMetadata(const std::string& key, const std::string& value) = 0;
    virtual std::string GetMetadata(const std::string& key) const = 0;
};

// ============================================================================
// W16: Stream Synchronization Interface
// ============================================================================

struct SyncStatus {
    int64_t timestamp_drift_ns;
    uint32_t corrections_applied;
    bool is_synchronized;
    double sync_confidence;
};

class IStreamSync {
public:
    virtual ~IStreamSync() = default;

    virtual bool Initialize(int num_streams) = 0;
    virtual bool Start() = 0;
    virtual bool Stop() = 0;

    // Synchronization
    virtual bool SyncFrame(int stream_id, uint64_t timestamp_ns) = 0;
    virtual bool WaitForSync(uint64_t timeout_ms) = 0;
    virtual int64_t GetTimestampDrift() const = 0;

    virtual SyncStatus GetSyncStatus() const = 0;
    virtual bool RecalibrateSync() = 0;
};

// ============================================================================
// W17: Preview Pipeline Interface
// ============================================================================

struct PreviewConfig {
    uint32_t width;
    uint32_t height;
    uint32_t framerate;
    uint32_t jpeg_quality;
    std::string stream_url;
    uint16_t port;
};

class IPreviewPipeline {
public:
    virtual ~IPreviewPipeline() = default;

    virtual bool Initialize(const PreviewConfig& config) = 0;
    virtual bool Start() = 0;
    virtual bool Stop() = 0;

    virtual bool IsStreaming() const = 0;
    virtual uint32_t GetConnectedClients() const = 0;
    virtual std::string GetStreamURL() const = 0;
};

// ============================================================================
// W18: Pipeline Monitor Interface
// ============================================================================

enum class AlertLevel {
    INFO,
    WARNING,
    ERROR,
    CRITICAL
};

struct Alert {
    AlertLevel level;
    std::string component;
    std::string message;
    uint64_t timestamp_ns;
};

using AlertCallback = std::function<void(const Alert&)>;

class IPipelineMonitor {
public:
    virtual ~IPipelineMonitor() = default;

    virtual bool Initialize() = 0;
    virtual bool Start() = 0;
    virtual bool Stop() = 0;

    // Monitoring
    virtual PipelineMetrics GetMetrics() const = 0;
    virtual std::vector<Alert> GetAlerts(uint32_t max_count) const = 0;
    virtual void RegisterAlertCallback(AlertCallback callback) = 0;

    // Frame drop detection
    virtual uint64_t GetTotalFrameDrops() const = 0;
    virtual bool IsHealthy() const = 0;
};

// ============================================================================
// W19: Storage Writer Interface
// ============================================================================

struct StorageStatus {
    uint64_t bytes_written;
    uint64_t bytes_available;
    double write_speed_mbps;
    bool is_writing;
    std::string current_file;
};

class IStorageWriter {
public:
    virtual ~IStorageWriter() = default;

    virtual bool Initialize(const std::string& output_dir) = 0;
    virtual bool OpenFile(const std::string& filename) = 0;
    virtual bool CloseFile() = 0;

    virtual bool WriteData(const void* data, size_t size) = 0;
    virtual bool Flush() = 0;

    virtual StorageStatus GetStatus() const = 0;
    virtual uint64_t GetAvailableSpace() const = 0;
    virtual bool HasEnoughSpace(uint64_t required_bytes) const = 0;
};

// ============================================================================
// W20: Recovery System Interface
// ============================================================================

enum class RecoveryAction {
    RESTART_PIPELINE,
    RESTART_CAMERA,
    RESTART_ENCODER,
    SALVAGE_RECORDING,
    FULL_RESET
};

struct RecoveryState {
    PipelineState last_known_state;
    std::string recovery_data_path;
    uint64_t frames_salvaged[2];
    bool partial_files_valid;
};

class IRecoverySystem {
public:
    virtual ~IRecoverySystem() = default;

    virtual bool Initialize(const std::string& state_dir) = 0;

    // State persistence
    virtual bool SaveState(const RecordingStatus& status) = 0;
    virtual bool LoadState(RecordingStatus& status) = 0;

    // Recovery
    virtual bool CanRecover() const = 0;
    virtual RecoveryAction DetermineAction() const = 0;
    virtual bool ExecuteRecovery(RecoveryAction action) = 0;

    // Salvage
    virtual bool SalvagePartialRecording(const std::string& partial_file) = 0;
    virtual RecoveryState GetRecoveryState() const = 0;
};

// ============================================================================
// Main Recording API (Public Interface)
// ============================================================================

class RecordingAPI {
public:
    RecordingAPI();
    ~RecordingAPI();

    // Initialize with all components
    bool Initialize(const std::string& config_path);
    bool Shutdown();

    // Recording control
    bool StartRecording(const std::string& game_id, const std::string& output_dir);
    RecordingResult StopRecording();

    // Status & Metrics
    RecordingStatus GetStatus() const;
    PipelineMetrics GetMetrics() const;
    bool IsRecording() const;

    // Camera control
    bool SetCameraExposure(int camera_id, uint32_t exposure_us);
    bool SetCameraGain(int camera_id, double gain);

    // Preview
    bool StartPreview(uint16_t port);
    bool StopPreview();

    // Monitoring
    void RegisterAlertCallback(AlertCallback callback);

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

// ============================================================================
// Frame Access API (for Processing Team)
// ============================================================================

using FrameCallback = std::function<void(const NVMMBuffer&)>;

class FrameAccessAPI {
public:
    FrameAccessAPI();
    ~FrameAccessAPI();

    bool Initialize();

    // Frame access (zero-copy)
    NVMMBuffer* GetFrameBuffer(int camera_id);
    void ReleaseFrameBuffer(NVMMBuffer* buffer);

    uint64_t GetTimestamp(int camera_id) const;

    // Frame subscription
    int SubscribeFrames(int camera_id, FrameCallback callback);
    bool UnsubscribeFrames(int subscription_id);

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace footballvision

#endif // FOOTBALLVISION_INTERFACES_H