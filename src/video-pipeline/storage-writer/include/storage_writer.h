/**
 * Storage Writer
 */

#ifndef FOOTBALLVISION_STORAGE_WRITER_H
#define FOOTBALLVISION_STORAGE_WRITER_H

#include "footballvision/interfaces.h"
#include <memory>
#include <string>

namespace footballvision {

class StorageWriter : public IStorageWriter {
public:
    static std::unique_ptr<StorageWriter> Create();

    StorageWriter();
    ~StorageWriter() override;

    bool Initialize(const std::string& output_dir) override;
    bool OpenFile(const std::string& filename) override;
    bool CloseFile() override;
    bool WriteData(const void* data, size_t size) override;
    bool Flush() override;
    StorageStatus GetStatus() const override;
    uint64_t GetAvailableSpace() const override;
    bool HasEnoughSpace(uint64_t required_bytes) const override;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
    std::string output_dir_;
};

} // namespace footballvision

#endif