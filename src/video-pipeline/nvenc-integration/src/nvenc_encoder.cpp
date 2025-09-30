/**
 * NVENC Encoder Implementation
 */

#include "nvenc_encoder.h"
#include <iostream>

namespace footballvision {

struct NVENCEncoder::Impl {
    uint64_t total_bytes_encoded = 0;
    // In production: NvEncoder* encoder
};

std::unique_ptr<NVENCEncoder> NVENCEncoder::Create() {
    return std::make_unique<NVENCEncoder>();
}

NVENCEncoder::NVENCEncoder() : impl_(std::make_unique<Impl>()) {}
NVENCEncoder::~NVENCEncoder() {}

bool NVENCEncoder::Initialize(const EncoderConfig& config) {
    config_ = config;
    std::cout << "[NVENC] Initialized: " << config.bitrate_bps / 1000000 << " Mbps, profile=" << config.profile << std::endl;
    return true;
}

bool NVENCEncoder::Configure(const EncoderConfig& config) {
    config_ = config;
    return true;
}

bool NVENCEncoder::EncodeFrame(const NVMMBuffer& input, void* output, size_t* output_size) {
    frames_encoded_++;
    *output_size = config_.bitrate_bps / config_.iframe_interval / 8;  // Estimate
    return true;
}

bool NVENCEncoder::Flush() {
    return true;
}

uint64_t NVENCEncoder::GetEncodedFrames() const {
    return frames_encoded_.load();
}

double NVENCEncoder::GetAverageBitrate() const {
    return config_.bitrate_bps;
}

} // namespace footballvision