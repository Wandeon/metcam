/**
 * FootballVision Pro - Main Recorder Application
 *
 * Coordinates all pipeline components for dual 4K camera recording
 */

#include "footballvision/interfaces.h"
#include "camera_control.h"
#include "gstreamer_pipeline.h"
#include "nvenc_encoder.h"
#include "recording_manager.h"
#include "stream_sync.h"
#include "preview_pipeline.h"
#include "pipeline_monitor.h"
#include "storage_writer.h"
#include "recovery_system.h"

#include <iostream>
#include <signal.h>
#include <unistd.h>
#include <memory>

using namespace footballvision;

// Global flag for graceful shutdown
static volatile bool g_running = true;

void signal_handler(int sig) {
    std::cout << "\n[Main] Received signal " << sig << ", shutting down..." << std::endl;
    g_running = false;
}

class FootballRecorder {
public:
    FootballRecorder() {
        std::cout << "========================================" << std::endl;
        std::cout << "  FootballVision Pro Recorder v1.0" << std::endl;
        std::cout << "========================================" << std::endl;
    }

    bool Initialize() {
        std::cout << "\n[Main] Initializing components..." << std::endl;

        // Initialize recovery system first
        recovery_ = RecoverySystem::Create();
        if (!recovery_->Initialize("/var/lib/footballvision/state")) {
            std::cerr << "Failed to initialize recovery system" << std::endl;
            return false;
        }

        // Check for crash recovery
        if (recovery_->CanRecover()) {
            std::cout << "[Main] Previous state detected, determining recovery action..." << std::endl;
            auto action = recovery_->DetermineAction();
            recovery_->ExecuteRecovery(action);
        }

        // Initialize monitoring
        monitor_ = PipelineMonitor::Create();
        if (!monitor_->Initialize()) {
            std::cerr << "Failed to initialize monitor" << std::endl;
            return false;
        }

        // Register alert callback
        monitor_->RegisterAlertCallback([](const Alert& alert) {
            std::cout << "[Alert] " << alert.component << ": " << alert.message << std::endl;
        });

        // Initialize cameras
        camera0_ = CameraControl::Create();
        camera1_ = CameraControl::Create();

        CameraConfig cam_config{
            .sensor_id = 0,
            .width = 4056,
            .height = 3040,
            .framerate = 30,
            .exposure_time_us = 1000,  // 1/1000s for sports
            .gain = 2.0,                // ISO 200
            .white_balance_mode = 1,    // Daylight
            .auto_exposure = false
        };

        if (!camera0_->Initialize(cam_config)) {
            std::cerr << "Failed to initialize camera 0" << std::endl;
            return false;
        }

        cam_config.sensor_id = 1;
        if (!camera1_->Initialize(cam_config)) {
            std::cerr << "Failed to initialize camera 1" << std::endl;
            return false;
        }

        // Initialize pipelines
        pipeline0_ = GStreamerPipeline::Create();
        pipeline1_ = GStreamerPipeline::Create();

        if (!pipeline0_->Initialize(0, "/tmp/camera0_output.mp4")) {
            std::cerr << "Failed to initialize pipeline 0" << std::endl;
            return false;
        }

        if (!pipeline1_->Initialize(1, "/tmp/camera1_output.mp4")) {
            std::cerr << "Failed to initialize pipeline 1" << std::endl;
            return false;
        }

        // Initialize synchronization
        sync_ = StreamSync::Create();
        if (!sync_->Initialize(2)) {
            std::cerr << "Failed to initialize sync" << std::endl;
            return false;
        }

        // Initialize storage
        storage0_ = StorageWriter::Create();
        storage1_ = StorageWriter::Create();

        if (!storage0_->Initialize("/mnt/recordings") ||
            !storage1_->Initialize("/mnt/recordings")) {
            std::cerr << "Failed to initialize storage" << std::endl;
            return false;
        }

        // Initialize preview (optional)
        preview_ = PreviewPipeline::Create();
        PreviewConfig preview_config{
            .width = 1280,
            .height = 720,
            .framerate = 15,
            .jpeg_quality = 75,
            .stream_url = "tcp://0.0.0.0:8554",
            .port = 8554
        };
        preview_->Initialize(preview_config);

        // Initialize recording manager
        recording_mgr_ = RecordingManager::Create();

        std::cout << "[Main] All components initialized successfully" << std::endl;
        return true;
    }

    bool StartRecording(const std::string& game_id) {
        std::cout << "\n[Main] Starting recording for game: " << game_id << std::endl;

        // Start monitoring
        monitor_->Start();

        // Start cameras
        if (!camera0_->Start() || !camera1_->Start()) {
            std::cerr << "Failed to start cameras" << std::endl;
            return false;
        }

        // Sync cameras
        camera1_->SyncWithMaster(camera0_.get());

        // Start sync
        sync_->Start();

        // Start pipelines
        if (!pipeline0_->Start() || !pipeline1_->Start()) {
            std::cerr << "Failed to start pipelines" << std::endl;
            return false;
        }

        // Start preview (non-critical)
        preview_->Start();

        // Start recording manager
        if (!recording_mgr_->StartRecording(game_id, "/mnt/recordings")) {
            std::cerr << "Failed to start recording manager" << std::endl;
            return false;
        }

        std::cout << "[Main] Recording started successfully" << std::endl;
        std::cout << "  Preview: " << preview_->GetStreamURL() << std::endl;

        return true;
    }

    bool StopRecording() {
        std::cout << "\n[Main] Stopping recording..." << std::endl;

        // Stop recording manager
        auto result = recording_mgr_->StopRecording();

        // Stop preview
        preview_->Stop();

        // Stop pipelines
        pipeline0_->Stop();
        pipeline1_->Stop();

        // Stop sync
        sync_->Stop();

        // Stop cameras
        camera0_->Stop();
        camera1_->Stop();

        // Stop monitoring
        monitor_->Stop();

        std::cout << "[Main] Recording stopped" << std::endl;
        std::cout << "  Camera 0: " << result.camera0_path << " (" << result.total_frames[0] << " frames)" << std::endl;
        std::cout << "  Camera 1: " << result.camera1_path << " (" << result.total_frames[1] << " frames)" << std::endl;
        std::cout << "  Duration: " << result.duration_ns / 1000000000 << " seconds" << std::endl;

        return result.success;
    }

    void MonitoringLoop() {
        std::cout << "\n[Main] Starting monitoring loop..." << std::endl;
        std::cout << "Press Ctrl+C to stop recording\n" << std::endl;

        while (g_running) {
            sleep(5);

            // Get metrics
            auto metrics = monitor_->GetMetrics();

            std::cout << "[Stats] "
                      << "Cam0: " << metrics.cameras[0].frames_captured << " frames, "
                      << metrics.cameras[0].frames_dropped << " drops | "
                      << "Cam1: " << metrics.cameras[1].frames_captured << " frames, "
                      << metrics.cameras[1].frames_dropped << " drops | "
                      << "Drift: " << sync_->GetTimestampDrift() / 1000000 << " ms"
                      << std::endl;

            // Check health
            if (!monitor_->IsHealthy()) {
                std::cout << "[Warning] Pipeline health check failed!" << std::endl;
            }

            // Save state for recovery
            auto status = recording_mgr_->GetStatus();
            recovery_->SaveState(status);
        }
    }

private:
    std::unique_ptr<CameraControl> camera0_;
    std::unique_ptr<CameraControl> camera1_;
    std::unique_ptr<GStreamerPipeline> pipeline0_;
    std::unique_ptr<GStreamerPipeline> pipeline1_;
    std::unique_ptr<StreamSync> sync_;
    std::unique_ptr<PreviewPipeline> preview_;
    std::unique_ptr<PipelineMonitor> monitor_;
    std::unique_ptr<StorageWriter> storage0_;
    std::unique_ptr<StorageWriter> storage1_;
    std::unique_ptr<RecordingManager> recording_mgr_;
    std::unique_ptr<RecoverySystem> recovery_;
};

int main(int argc, char* argv[]) {
    // Set up signal handlers
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    // Get game ID from command line or use default
    std::string game_id = "game_test";
    if (argc > 1) {
        game_id = argv[1];
    }

    FootballRecorder recorder;

    if (!recorder.Initialize()) {
        std::cerr << "Failed to initialize recorder" << std::endl;
        return 1;
    }

    if (!recorder.StartRecording(game_id)) {
        std::cerr << "Failed to start recording" << std::endl;
        return 1;
    }

    // Monitor until signal
    recorder.MonitoringLoop();

    if (!recorder.StopRecording()) {
        std::cerr << "Failed to stop recording cleanly" << std::endl;
        return 1;
    }

    std::cout << "\n========================================" << std::endl;
    std::cout << "  Recording completed successfully" << std::endl;
    std::cout << "========================================" << std::endl;

    return 0;
}