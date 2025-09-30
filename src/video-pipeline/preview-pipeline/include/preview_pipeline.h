/**
 * Preview Pipeline
 */

#ifndef FOOTBALLVISION_PREVIEW_PIPELINE_H
#define FOOTBALLVISION_PREVIEW_PIPELINE_H

#include "footballvision/interfaces.h"
#include <memory>

namespace footballvision {

class PreviewPipeline : public IPreviewPipeline {
public:
    static std::unique_ptr<PreviewPipeline> Create();

    PreviewPipeline();
    ~PreviewPipeline() override;

    bool Initialize(const PreviewConfig& config) override;
    bool Start() override;
    bool Stop() override;
    bool IsStreaming() const override;
    uint32_t GetConnectedClients() const override;
    std::string GetStreamURL() const override;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
    PreviewConfig config_;
};

} // namespace footballvision

#endif