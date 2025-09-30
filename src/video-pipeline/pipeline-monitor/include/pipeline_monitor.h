/**
 * Pipeline Monitor
 */

#ifndef FOOTBALLVISION_PIPELINE_MONITOR_H
#define FOOTBALLVISION_PIPELINE_MONITOR_H

#include "footballvision/interfaces.h"
#include <memory>
#include <vector>
#include <deque>

namespace footballvision {

class PipelineMonitor : public IPipelineMonitor {
public:
    static std::unique_ptr<PipelineMonitor> Create();

    PipelineMonitor();
    ~PipelineMonitor() override;

    bool Initialize() override;
    bool Start() override;
    bool Stop() override;
    PipelineMetrics GetMetrics() const override;
    std::vector<Alert> GetAlerts(uint32_t max_count) const override;
    void RegisterAlertCallback(AlertCallback callback) override;
    uint64_t GetTotalFrameDrops() const override;
    bool IsHealthy() const override;

    void RecordFrameCapture(int camera_id);
    void RecordFrameDrop(int camera_id);

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace footballvision

#endif