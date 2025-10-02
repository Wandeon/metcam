#include "storage_manager.h"
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>

struct StorageManager {
    char output_dir[256];
    int fd;
    uint64_t bytes_written;
};

StorageManager* storage_manager_create(const char* output_dir) {
    StorageManager* mgr = malloc(sizeof(StorageManager));
    strncpy(mgr->output_dir, output_dir, 255);
    mgr->fd = -1;
    mgr->bytes_written = 0;
    return mgr;
}

int storage_manager_open_file(StorageManager* mgr, const char* filename) {
    char path[512];
    snprintf(path, 512, "%s/%s", mgr->output_dir, filename);

    // O_DIRECT for zero-copy writes
    mgr->fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);

    if (mgr->fd < 0) return -1;

    // Pre-allocate 50GB for recording
    posix_fallocate(mgr->fd, 0, 50L * 1024 * 1024 * 1024);
    return 0;
}

ssize_t storage_manager_write(StorageManager* mgr, const void* data, size_t size) {
    if (mgr->fd < 0) return -1;

    ssize_t written = write(mgr->fd, data, size);
    if (written > 0) {
        mgr->bytes_written += written;
    }
    return written;
}

int storage_manager_close_file(StorageManager* mgr) {
    if (mgr->fd >= 0) {
        fsync(mgr->fd);
        close(mgr->fd);
        mgr->fd = -1;
    }
    return 0;
}

uint64_t storage_manager_get_available_space(const char* path) {
    struct statvfs stat;
    if (statvfs(path, &stat) != 0) return 0;
    return (uint64_t)stat.f_bavail * stat.f_frsize;
}

void storage_manager_destroy(StorageManager* mgr) {
    storage_manager_close_file(mgr);
    free(mgr);
}
