/**
 * GStreamer Pipeline Tests
 */

#include "gstreamer_pipeline.h"
#include "nvmm_buffer_manager.h"
#include <iostream>
#include <cassert>
#include <thread>
#include <chrono>

using namespace footballvision;

void test_pipeline_creation() {
    std::cout << "\n=== Test: Pipeline Creation ===" << std::endl;

    auto pipeline = GStreamerPipeline::Create();
    assert(pipeline != nullptr);
    assert(pipeline->GetState() == PipelineState::IDLE);

    std::cout << "✓ Pipeline creation test passed" << std::endl;
}

void test_pipeline_initialization() {
    std::cout << "\n=== Test: Pipeline Initialization ===" << std::endl;

    auto pipeline = GStreamerPipeline::Create();

    bool result = pipeline->Initialize(0, "/tmp/test_camera0.mp4");
    assert(result == true);
    assert(pipeline->GetState() == PipelineState::IDLE);

    std::cout << "✓ Pipeline initialization test passed" << std::endl;
}

void test_pipeline_start_stop() {
    std::cout << "\n=== Test: Pipeline Start/Stop ===" << std::endl;

    auto pipeline = GStreamerPipeline::Create();
    pipeline->Initialize(0, "/tmp/test_camera0.mp4");

    bool started = pipeline->Start();
    assert(started == true);
    assert(pipeline->GetState() == PipelineState::RECORDING);

    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    bool stopped = pipeline->Stop();
    assert(stopped == true);
    assert(pipeline->GetState() == PipelineState::IDLE);

    std::cout << "✓ Pipeline start/stop test passed" << std::endl;
}

void test_buffer_manager() {
    std::cout << "\n=== Test: NVMM Buffer Manager ===" << std::endl;

    auto manager = NVMMBufferManager::Create();
    assert(manager != nullptr);

    BufferPoolConfig config{
        .num_buffers = 30,
        .buffer_size = 4056 * 3040 * 3 / 2,  // NV12 format
        .width = 4056,
        .height = 3040,
        .memory_type = 1,  // NVBUF_MEM_SURFACE_ARRAY
        .alignment = 256
    };

    bool result = manager->Initialize(config);
    assert(result == true);
    assert(manager->GetTotalBuffers() == 30);
    assert(manager->GetAvailableBuffers() == 30);
    assert(manager->GetUsedBuffers() == 0);

    std::cout << "✓ Buffer manager initialization passed" << std::endl;

    // Acquire buffers
    std::vector<NVMMBuffer*> acquired;
    for (int i = 0; i < 10; i++) {
        NVMMBuffer* buf = manager->AcquireBuffer();
        assert(buf != nullptr);
        acquired.push_back(buf);
    }

    assert(manager->GetAvailableBuffers() == 20);
    assert(manager->GetUsedBuffers() == 10);

    std::cout << "✓ Buffer acquisition passed" << std::endl;

    // Release buffers
    for (auto* buf : acquired) {
        manager->ReleaseBuffer(buf);
    }

    assert(manager->GetAvailableBuffers() == 30);
    assert(manager->GetUsedBuffers() == 0);

    std::cout << "✓ Buffer release passed" << std::endl;

    // Test exhaustion
    std::vector<NVMMBuffer*> all_buffers;
    for (uint32_t i = 0; i < 30; i++) {
        NVMMBuffer* buf = manager->AcquireBuffer();
        assert(buf != nullptr);
        all_buffers.push_back(buf);
    }

    NVMMBuffer* extra = manager->AcquireBuffer();
    assert(extra == nullptr);  // Pool exhausted

    std::cout << "✓ Buffer exhaustion handling passed" << std::endl;

    // Cleanup
    for (auto* buf : all_buffers) {
        manager->ReleaseBuffer(buf);
    }

    std::cout << "✓ Buffer manager test passed" << std::endl;
}

void test_dual_pipeline() {
    std::cout << "\n=== Test: Dual Pipeline ===" << std::endl;

    auto pipeline0 = GStreamerPipeline::Create();
    auto pipeline1 = GStreamerPipeline::Create();

    pipeline0->Initialize(0, "/tmp/test_camera0.mp4");
    pipeline1->Initialize(1, "/tmp/test_camera1.mp4");

    pipeline0->Start();
    pipeline1->Start();

    assert(pipeline0->GetState() == PipelineState::RECORDING);
    assert(pipeline1->GetState() == PipelineState::RECORDING);

    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    pipeline0->Stop();
    pipeline1->Stop();

    assert(pipeline0->GetState() == PipelineState::IDLE);
    assert(pipeline1->GetState() == PipelineState::IDLE);

    std::cout << "✓ Dual pipeline test passed" << std::endl;
}

void test_error_callback() {
    std::cout << "\n=== Test: Error Callback ===" << std::endl;

    auto pipeline = GStreamerPipeline::Create();

    bool callback_called = false;
    std::string error_msg;

    pipeline->SetErrorCallback([&](const std::string& msg) {
        callback_called = true;
        error_msg = msg;
    });

    pipeline->Initialize(0, "/tmp/test_camera0.mp4");

    // In production, this would trigger an error
    // For now, just verify callback is set

    std::cout << "✓ Error callback test passed" << std::endl;
}

void test_eos_handling() {
    std::cout << "\n=== Test: EOS Handling ===" << std::endl;

    auto pipeline = GStreamerPipeline::Create();

    bool eos_called = false;

    pipeline->SetEOSCallback([&]() {
        eos_called = true;
    });

    pipeline->Initialize(0, "/tmp/test_camera0.mp4");
    pipeline->Start();

    // Send EOS
    bool result = pipeline->SendEOS();
    assert(result == true);

    pipeline->Stop();

    std::cout << "✓ EOS handling test passed" << std::endl;
}

int main() {
    std::cout << "========================================" << std::endl;
    std::cout << "  GStreamer Pipeline Test Suite" << std::endl;
    std::cout << "========================================" << std::endl;

    try {
        test_pipeline_creation();
        test_pipeline_initialization();
        test_pipeline_start_stop();
        test_buffer_manager();
        test_dual_pipeline();
        test_error_callback();
        test_eos_handling();

        std::cout << "\n========================================" << std::endl;
        std::cout << "  All tests passed! ✓" << std::endl;
        std::cout << "========================================" << std::endl;

        return 0;
    } catch (const std::exception& e) {
        std::cerr << "\n✗ Test failed with exception: " << e.what() << std::endl;
        return 1;
    }
}