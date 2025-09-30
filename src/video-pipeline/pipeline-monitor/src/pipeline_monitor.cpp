/**
 * Pipeline Monitor Implementation
 */

#include "pipeline_monitor.h"
#include <iostream>
#include <chrono>

namespace footballvision {

struct PipelineMonitor::Impl {
    uint64_t frames_captured[2] = {0, 0};
    uint64_t frames_dropped[2] = {0, 0};
    std::deque<Alert> alerts;
    std::vector<AlertCallback> callbacks;
    bool running = false;

    void AddAlert(AlertLevel level, const std::string& component, const std::string& message) {
        Alert alert;
        alert.level = level;
        alert.component = component;
        alert.message = message;
        alert.timestamp_ns = std::chrono::steady_clock::now().time_since_epoch().count();

        alerts.push_back(alert);
        if (alerts.size() > 1000) alerts.pop_front();

        for (auto& cb : callbacks) {
            cb(alert);
        }
    }
};

std::unique_ptr<PipelineMonitor> PipelineMonitor::Create() {
    return std::make_unique<PipelineMonitor>();
}

PipelineMonitor::PipelineMonitor() : impl_(std::make_unique<Impl>()) {}
PipelineMonitor::~PipelineMonitor() {}

bool PipelineMonitor::Initialize() {
    std::cout << "[PipelineMonitor] Initialized" << std::endl;
    return true;
}

bool PipelineMonitor::Start() {
    impl_->running = true;
    impl_->AddAlert(AlertLevel::INFO, "Monitor", "Pipeline monitoring started");
    return true;
}

bool PipelineMonitor::Stop() {
    impl_->running = false;
    return true;
}

PipelineMetrics PipelineMonitor::GetMetrics() const {
    PipelineMetrics metrics{};
    for (int i = 0; i < 2; i++) {
        metrics.cameras[i].frames_captured = impl_->frames_captured[i];
        metrics.cameras[i].frames_dropped = impl_->frames_dropped[i];
        metrics.cameras[i].current_fps = 30.0;  // Mock
        metrics.cameras[i].average_fps = 30.0;
    }
    return metrics;
}

std::vector<Alert> PipelineMonitor::GetAlerts(uint32_t max_count) const {
    std::vector<Alert> result;
    auto it = impl_->alerts.rbegin();
    for (uint32_t i = 0; i < max_count && it != impl_->alerts.rend(); i++, ++it) {
        result.push_back(*it);
    }
    return result;
}

void PipelineMonitor::RegisterAlertCallback(AlertCallback callback) {
    impl_->callbacks.push_back(callback);
}

uint64_t PipelineMonitor::GetTotalFrameDrops() const {
    return impl_->frames_dropped[0] + impl_->frames_dropped[1];
}

bool PipelineMonitor::IsHealthy() const {
    return impl_->running && GetTotalFrameDrops() == 0;
}

void PipelineMonitor::RecordFrameCapture(int camera_id) {
    if (camera_id >= 0 && camera_id < 2) {
        impl_->frames_captured[camera_id]++;
    }
}

void PipelineMonitor::RecordFrameDrop(int camera_id) {
    if (camera_id >= 0 && camera_id < 2) {
        impl_->frames_dropped[camera_id]++;
        impl_->AddAlert(AlertLevel::WARNING, "Camera" + std::to_string(camera_id),
                       "Frame drop detected");
    }
}

} // namespace footballvision