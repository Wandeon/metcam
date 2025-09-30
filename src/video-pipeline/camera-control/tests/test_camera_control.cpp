/**
 * Camera Control Unit Tests
 */

#include "camera_control.h"
#include <iostream>
#include <cassert>
#include <thread>
#include <chrono>

using namespace footballvision;

void test_initialization() {
    std::cout << "\n=== Test: Camera Initialization ===" << std::endl;

    auto camera = CameraControl::Create();
    assert(camera != nullptr);

    CameraConfig config{
        .sensor_id = 0,
        .width = 4056,
        .height = 3040,
        .framerate = 30,
        .exposure_time_us = 1000,
        .gain = 2.0,
        .white_balance_mode = 1,
        .auto_exposure = false
    };

    bool result = camera->Initialize(config);
    assert(result == true);
    assert(camera->GetExposure() == 1000);
    assert(camera->GetGain() == 2.0);

    std::cout << "✓ Initialization test passed" << std::endl;
}

void test_start_stop() {
    std::cout << "\n=== Test: Start/Stop ===" << std::endl;

    auto camera = CameraControl::Create();

    CameraConfig config{
        .sensor_id = 0,
        .width = 4056,
        .height = 3040,
        .framerate = 30,
        .exposure_time_us = 1000,
        .gain = 2.0,
        .white_balance_mode = 1,
        .auto_exposure = false
    };

    camera->Initialize(config);

    assert(camera->IsRunning() == false);

    bool started = camera->Start();
    assert(started == true);
    assert(camera->IsRunning() == true);

    std::this_thread::sleep_for(std::chrono::milliseconds(100));

    bool stopped = camera->Stop();
    assert(stopped == true);
    assert(camera->IsRunning() == false);

    std::cout << "✓ Start/Stop test passed" << std::endl;
}

void test_exposure_control() {
    std::cout << "\n=== Test: Exposure Control ===" << std::endl;

    auto camera = CameraControl::Create();

    CameraConfig config{
        .sensor_id = 0,
        .width = 4056,
        .height = 3040,
        .framerate = 30,
        .exposure_time_us = 1000,
        .gain = 2.0,
        .white_balance_mode = 1,
        .auto_exposure = false
    };

    camera->Initialize(config);
    camera->Start();

    // Valid exposure
    bool result = camera->SetExposure(800);
    assert(result == true);
    assert(camera->GetExposure() == 800);

    // Another valid value
    result = camera->SetExposure(1500);
    assert(result == true);
    assert(camera->GetExposure() == 1500);

    // Invalid exposure (too low)
    result = camera->SetExposure(100);
    assert(result == false);
    assert(camera->GetExposure() == 1500);  // Unchanged

    // Invalid exposure (too high)
    result = camera->SetExposure(5000);
    assert(result == false);
    assert(camera->GetExposure() == 1500);  // Unchanged

    camera->Stop();

    std::cout << "✓ Exposure control test passed" << std::endl;
}

void test_gain_control() {
    std::cout << "\n=== Test: Gain Control ===" << std::endl;

    auto camera = CameraControl::Create();

    CameraConfig config{
        .sensor_id = 0,
        .width = 4056,
        .height = 3040,
        .framerate = 30,
        .exposure_time_us = 1000,
        .gain = 2.0,
        .white_balance_mode = 1,
        .auto_exposure = false
    };

    camera->Initialize(config);
    camera->Start();

    // Valid gain
    bool result = camera->SetGain(1.5);
    assert(result == true);
    assert(camera->GetGain() == 1.5);

    // Another valid value
    result = camera->SetGain(3.0);
    assert(result == true);
    assert(camera->GetGain() == 3.0);

    // Invalid gain (too low)
    result = camera->SetGain(0.5);
    assert(result == false);
    assert(camera->GetGain() == 3.0);  // Unchanged

    // Invalid gain (too high)
    result = camera->SetGain(10.0);
    assert(result == false);
    assert(camera->GetGain() == 3.0);  // Unchanged

    camera->Stop();

    std::cout << "✓ Gain control test passed" << std::endl;
}

void test_dual_camera() {
    std::cout << "\n=== Test: Dual Camera Setup ===" << std::endl;

    auto camera0 = CameraControl::Create();
    auto camera1 = CameraControl::Create();

    CameraConfig config0{
        .sensor_id = 0,
        .width = 4056,
        .height = 3040,
        .framerate = 30,
        .exposure_time_us = 1000,
        .gain = 2.0,
        .white_balance_mode = 1,
        .auto_exposure = false
    };

    CameraConfig config1 = config0;
    config1.sensor_id = 1;

    camera0->Initialize(config0);
    camera1->Initialize(config1);

    camera0->Start();
    camera1->Start();

    assert(camera0->IsRunning() == true);
    assert(camera1->IsRunning() == true);

    // Sync camera1 with camera0 (master)
    bool synced = camera1->SyncWithMaster(camera0.get());
    assert(synced == true);

    std::this_thread::sleep_for(std::chrono::milliseconds(100));

    camera0->Stop();
    camera1->Stop();

    std::cout << "✓ Dual camera test passed" << std::endl;
}

void test_timestamp() {
    std::cout << "\n=== Test: Frame Timestamps ===" << std::endl;

    auto camera = CameraControl::Create();

    CameraConfig config{
        .sensor_id = 0,
        .width = 4056,
        .height = 3040,
        .framerate = 30,
        .exposure_time_us = 1000,
        .gain = 2.0,
        .white_balance_mode = 1,
        .auto_exposure = false
    };

    camera->Initialize(config);
    camera->Start();

    uint64_t ts1 = camera->GetFrameTimestamp();
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    uint64_t ts2 = camera->GetFrameTimestamp();

    assert(ts2 > ts1);
    assert((ts2 - ts1) >= 50000000);  // At least 50ms difference

    camera->Stop();

    std::cout << "✓ Timestamp test passed" << std::endl;
}

int main() {
    std::cout << "========================================" << std::endl;
    std::cout << "  Camera Control Test Suite" << std::endl;
    std::cout << "========================================" << std::endl;

    try {
        test_initialization();
        test_start_stop();
        test_exposure_control();
        test_gain_control();
        test_dual_camera();
        test_timestamp();

        std::cout << "\n========================================" << std::endl;
        std::cout << "  All tests passed! ✓" << std::endl;
        std::cout << "========================================" << std::endl;

        return 0;
    } catch (const std::exception& e) {
        std::cerr << "\n✗ Test failed with exception: " << e.what() << std::endl;
        return 1;
    }
}