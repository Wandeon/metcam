/**
 * Recording Manager Implementation
 */

#include "recording_manager.h"
#include <iostream>
#include <chrono>

namespace footballvision {

struct RecordingManager::Impl {
    PipelineState state = PipelineState::IDLE;
    std::string game_id;
    std::string output_dir;
    std::chrono::steady_clock::time_point start_time;
    uint64_t frames_recorded[2] = {0, 0};
};

std::unique_ptr<RecordingManager> RecordingManager::Create() {
    return std::make_unique<RecordingManager>();
}

RecordingManager::RecordingManager() : impl_(std::make_unique<Impl>()) {}
RecordingManager::~RecordingManager() {}

bool RecordingManager::StartRecording(const std::string& game_id, const std::string& output_dir) {
    std::cout << "[RecordingManager] Starting recording: " << game_id << std::endl;
    impl_->state = PipelineState::STARTING;
    impl_->game_id = game_id;
    impl_->output_dir = output_dir;
    impl_->start_time = std::chrono::steady_clock::now();
    impl_->state = PipelineState::RECORDING;
    return true;
}

RecordingResult RecordingManager::StopRecording() {
    std::cout << "[RecordingManager] Stopping recording..." << std::endl;
    impl_->state = PipelineState::STOPPING;

    RecordingResult result;
    result.success = true;
    result.camera0_path = impl_->output_dir + "/" + impl_->game_id + "_cam0.mp4";
    result.camera1_path = impl_->output_dir + "/" + impl_->game_id + "_cam1.mp4";
    result.duration_ns = GetRecordingDuration();
    result.total_frames[0] = impl_->frames_recorded[0];
    result.total_frames[1] = impl_->frames_recorded[1];

    impl_->state = PipelineState::IDLE;
    return result;
}

RecordingStatus RecordingManager::GetStatus() const {
    RecordingStatus status;
    status.state = impl_->state;
    status.frames_recorded[0] = impl_->frames_recorded[0];
    status.frames_recorded[1] = impl_->frames_recorded[1];
    status.duration_ns = GetRecordingDuration();
    return status;
}

PipelineMetrics RecordingManager::GetMetrics() const {
    return PipelineMetrics{};
}

bool RecordingManager::IsRecording() const {
    return impl_->state == PipelineState::RECORDING;
}

uint64_t RecordingManager::GetRecordingDuration() const {
    if (impl_->state == PipelineState::IDLE) return 0;
    auto now = std::chrono::steady_clock::now();
    return std::chrono::duration_cast<std::chrono::nanoseconds>(now - impl_->start_time).count();
}

bool RecordingManager::SetMetadata(const std::string& key, const std::string& value) {
    metadata_[key] = value;
    return true;
}

std::string RecordingManager::GetMetadata(const std::string& key) const {
    auto it = metadata_.find(key);
    return (it != metadata_.end()) ? it->second : "";
}

} // namespace footballvision