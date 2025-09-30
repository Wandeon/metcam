/**
 * Stream Synchronization Implementation
 */

#include "stream_sync.h"
#include <iostream>

namespace footballvision {

struct StreamSync::Impl {
    int num_streams = 0;
    std::vector<uint64_t> last_timestamps;
    uint32_t corrections = 0;
    int64_t max_drift_ns = 0;
};

std::unique_ptr<StreamSync> StreamSync::Create() {
    return std::make_unique<StreamSync>();
}

StreamSync::StreamSync() : impl_(std::make_unique<Impl>()) {}
StreamSync::~StreamSync() {}

bool StreamSync::Initialize(int num_streams) {
    impl_->num_streams = num_streams;
    impl_->last_timestamps.resize(num_streams, 0);
    std::cout << "[StreamSync] Initialized for " << num_streams << " streams" << std::endl;
    return true;
}

bool StreamSync::Start() {
    running_ = true;
    return true;
}

bool StreamSync::Stop() {
    running_ = false;
    return true;
}

bool StreamSync::SyncFrame(int stream_id, uint64_t timestamp_ns) {
    if (stream_id >= impl_->num_streams) return false;
    impl_->last_timestamps[stream_id] = timestamp_ns;

    // Calculate drift
    if (impl_->num_streams == 2) {
        int64_t drift = impl_->last_timestamps[0] - impl_->last_timestamps[1];
        impl_->max_drift_ns = std::max(impl_->max_drift_ns, std::abs(drift));

        // Apply correction if drift > 16ms
        if (std::abs(drift) > 16000000) {
            impl_->corrections++;
        }
    }
    return true;
}

bool StreamSync::WaitForSync(uint64_t timeout_ms) {
    return true;
}

int64_t StreamSync::GetTimestampDrift() const {
    if (impl_->num_streams != 2) return 0;
    return impl_->last_timestamps[0] - impl_->last_timestamps[1];
}

SyncStatus StreamSync::GetSyncStatus() const {
    SyncStatus status;
    status.timestamp_drift_ns = GetTimestampDrift();
    status.corrections_applied = impl_->corrections;
    status.is_synchronized = std::abs(status.timestamp_drift_ns) < 33000000;  // <1 frame
    status.sync_confidence = status.is_synchronized ? 1.0 : 0.5;
    return status;
}

bool StreamSync::RecalibrateSync() {
    impl_->corrections = 0;
    impl_->max_drift_ns = 0;
    std::cout << "[StreamSync] Recalibrated" << std::endl;
    return true;
}

} // namespace footballvision