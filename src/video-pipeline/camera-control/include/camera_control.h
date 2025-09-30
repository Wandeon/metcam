/**
 * Camera Control Module
 * libargus wrapper for IMX477 sensors
 */

#ifndef FOOTBALLVISION_CAMERA_CONTROL_H
#define FOOTBALLVISION_CAMERA_CONTROL_H

#include "footballvision/interfaces.h"
#include <memory>
#include <atomic>
#include <mutex>

namespace footballvision {

class CameraControl : public ICameraControl {
public:
    static std::unique_ptr<CameraControl> Create();

    CameraControl();
    ~CameraControl() override;

    // ICameraControl implementation
    bool Initialize(const CameraConfig& config) override;
    bool Start() override;
    bool Stop() override;

    bool SetExposure(uint32_t exposure_us) override;
    bool SetGain(double gain) override;
    bool SetWhiteBalance(int mode) override;
    bool EnableAutoExposure(bool enable) override;

    uint32_t GetExposure() const override;
    double GetGain() const override;
    bool IsRunning() const override;

    // Extended API
    bool SetFrameRate(uint32_t fps);
    bool TriggerAutoWhiteBalance();

    // Synchronization support
    bool SyncWithMaster(CameraControl* master);
    uint64_t GetFrameTimestamp() const;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;

    CameraConfig config_;
    std::atomic<bool> running_;
    mutable std::mutex mutex_;
};

} // namespace footballvision

#endif // FOOTBALLVISION_CAMERA_CONTROL_H