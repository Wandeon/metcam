/**
 * Stream Synchronization
 */

#ifndef FOOTBALLVISION_STREAM_SYNC_H
#define FOOTBALLVISION_STREAM_SYNC_H

#include "footballvision/interfaces.h"
#include <memory>
#include <atomic>
#include <vector>

namespace footballvision {

class StreamSync : public IStreamSync {
public:
    static std::unique_ptr<StreamSync> Create();

    StreamSync();
    ~StreamSync() override;

    bool Initialize(int num_streams) override;
    bool Start() override;
    bool Stop() override;
    bool SyncFrame(int stream_id, uint64_t timestamp_ns) override;
    bool WaitForSync(uint64_t timeout_ms) override;
    int64_t GetTimestampDrift() const override;
    SyncStatus GetSyncStatus() const override;
    bool RecalibrateSync() override;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
    std::atomic<bool> running_{false};
};

} // namespace footballvision

#endif