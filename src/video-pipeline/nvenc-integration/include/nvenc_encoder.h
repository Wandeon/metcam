/**
 * NVENC Encoder Wrapper
 */

#ifndef FOOTBALLVISION_NVENC_ENCODER_H
#define FOOTBALLVISION_NVENC_ENCODER_H

#include "footballvision/interfaces.h"
#include <memory>
#include <atomic>

namespace footballvision {

class NVENCEncoder : public INVENCEncoder {
public:
    static std::unique_ptr<NVENCEncoder> Create();

    NVENCEncoder();
    ~NVENCEncoder() override;

    bool Initialize(const EncoderConfig& config) override;
    bool Configure(const EncoderConfig& config) override;
    bool EncodeFrame(const NVMMBuffer& input, void* output, size_t* output_size) override;
    bool Flush() override;

    uint64_t GetEncodedFrames() const override;
    double GetAverageBitrate() const override;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
    EncoderConfig config_;
    std::atomic<uint64_t> frames_encoded_{0};
};

} // namespace footballvision

#endif