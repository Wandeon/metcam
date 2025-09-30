/**
 * Recovery System
 */

#ifndef FOOTBALLVISION_RECOVERY_SYSTEM_H
#define FOOTBALLVISION_RECOVERY_SYSTEM_H

#include "footballvision/interfaces.h"
#include <memory>
#include <string>

namespace footballvision {

class RecoverySystem : public IRecoverySystem {
public:
    static std::unique_ptr<RecoverySystem> Create();

    RecoverySystem();
    ~RecoverySystem() override;

    bool Initialize(const std::string& state_dir) override;
    bool SaveState(const RecordingStatus& status) override;
    bool LoadState(RecordingStatus& status) override;
    bool CanRecover() const override;
    RecoveryAction DetermineAction() const override;
    bool ExecuteRecovery(RecoveryAction action) override;
    bool SalvagePartialRecording(const std::string& partial_file) override;
    RecoveryState GetRecoveryState() const override;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
    std::string state_dir_;
};

} // namespace footballvision

#endif