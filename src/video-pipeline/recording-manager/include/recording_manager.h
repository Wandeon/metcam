/**
 * Recording Manager
 */

#ifndef FOOTBALLVISION_RECORDING_MANAGER_H
#define FOOTBALLVISION_RECORDING_MANAGER_H

#include "footballvision/interfaces.h"
#include <memory>
#include <string>
#include <map>

namespace footballvision {

class RecordingManager : public IRecordingManager {
public:
    static std::unique_ptr<RecordingManager> Create();

    RecordingManager();
    ~RecordingManager() override;

    bool StartRecording(const std::string& game_id, const std::string& output_dir) override;
    RecordingResult StopRecording() override;
    RecordingStatus GetStatus() const override;
    PipelineMetrics GetMetrics() const override;
    bool IsRecording() const override;
    uint64_t GetRecordingDuration() const override;
    bool SetMetadata(const std::string& key, const std::string& value) override;
    std::string GetMetadata(const std::string& key) const override;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
    std::map<std::string, std::string> metadata_;
};

} // namespace footballvision

#endif