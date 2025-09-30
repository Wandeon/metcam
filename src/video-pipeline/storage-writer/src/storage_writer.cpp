/**
 * Storage Writer Implementation
 */

#include "storage_writer.h"
#include <iostream>
#include <fstream>
#include <sys/statvfs.h>

namespace footballvision {

struct StorageWriter::Impl {
    std::ofstream file;
    uint64_t bytes_written = 0;
    std::string current_file;
    bool is_writing = false;
};

std::unique_ptr<StorageWriter> StorageWriter::Create() {
    return std::make_unique<StorageWriter>();
}

StorageWriter::StorageWriter() : impl_(std::make_unique<Impl>()) {}
StorageWriter::~StorageWriter() { CloseFile(); }

bool StorageWriter::Initialize(const std::string& output_dir) {
    output_dir_ = output_dir;
    std::cout << "[StorageWriter] Initialized: " << output_dir << std::endl;
    return true;
}

bool StorageWriter::OpenFile(const std::string& filename) {
    std::string path = output_dir_ + "/" + filename;
    impl_->file.open(path, std::ios::binary);
    if (!impl_->file.is_open()) {
        std::cerr << "[StorageWriter] Failed to open: " << path << std::endl;
        return false;
    }
    impl_->current_file = path;
    impl_->is_writing = true;
    impl_->bytes_written = 0;
    std::cout << "[StorageWriter] Opened: " << path << std::endl;
    return true;
}

bool StorageWriter::CloseFile() {
    if (impl_->file.is_open()) {
        impl_->file.close();
        std::cout << "[StorageWriter] Closed: " << impl_->current_file
                  << " (" << impl_->bytes_written / 1024 / 1024 << " MB)" << std::endl;
    }
    impl_->is_writing = false;
    return true;
}

bool StorageWriter::WriteData(const void* data, size_t size) {
    if (!impl_->is_writing) return false;
    impl_->file.write(static_cast<const char*>(data), size);
    impl_->bytes_written += size;
    return true;
}

bool StorageWriter::Flush() {
    if (impl_->is_writing) {
        impl_->file.flush();
    }
    return true;
}

StorageStatus StorageWriter::GetStatus() const {
    StorageStatus status;
    status.bytes_written = impl_->bytes_written;
    status.bytes_available = GetAvailableSpace();
    status.write_speed_mbps = 100.0;  // Mock
    status.is_writing = impl_->is_writing;
    status.current_file = impl_->current_file;
    return status;
}

uint64_t StorageWriter::GetAvailableSpace() const {
    struct statvfs stat;
    if (statvfs(output_dir_.c_str(), &stat) != 0) {
        return 0;
    }
    return stat.f_bavail * stat.f_frsize;
}

bool StorageWriter::HasEnoughSpace(uint64_t required_bytes) const {
    return GetAvailableSpace() >= required_bytes;
}

} // namespace footballvision