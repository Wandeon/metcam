/**
 * Preview Pipeline Implementation
 */

#include "preview_pipeline.h"
#include <iostream>
#include <sstream>

namespace footballvision {

struct PreviewPipeline::Impl {
    bool streaming = false;
    uint32_t clients = 0;
};

std::unique_ptr<PreviewPipeline> PreviewPipeline::Create() {
    return std::make_unique<PreviewPipeline>();
}

PreviewPipeline::PreviewPipeline() : impl_(std::make_unique<Impl>()) {}
PreviewPipeline::~PreviewPipeline() { Stop(); }

bool PreviewPipeline::Initialize(const PreviewConfig& config) {
    config_ = config;
    std::cout << "[PreviewPipeline] Initialized: " << config.width << "x" << config.height
              << " @ " << config.framerate << "fps on port " << config.port << std::endl;
    return true;
}

bool PreviewPipeline::Start() {
    std::cout << "[PreviewPipeline] Starting preview stream..." << std::endl;
    impl_->streaming = true;
    return true;
}

bool PreviewPipeline::Stop() {
    impl_->streaming = false;
    return true;
}

bool PreviewPipeline::IsStreaming() const {
    return impl_->streaming;
}

uint32_t PreviewPipeline::GetConnectedClients() const {
    return impl_->clients;
}

std::string PreviewPipeline::GetStreamURL() const {
    std::stringstream ss;
    ss << "tcp://0.0.0.0:" << config_.port;
    return ss.str();
}

} // namespace footballvision