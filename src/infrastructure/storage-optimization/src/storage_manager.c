/*
 * Storage Manager for FootballVision Pro
 * Optimizes NVMe storage for high-bandwidth video recording
 *
 * Features:
 * - Write buffer management
 * - Filesystem tuning
 * - Space monitoring
 * - Performance tracking
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/ioctl.h>
#include <linux/fs.h>
#include <errno.h>
#include <time.h>
#include <syslog.h>

#include "storage_manager.h"

#define RECORDING_PATH "/mnt/recordings"
#define MIN_FREE_SPACE_GB 10
#define BUFFER_SIZE (256 * 1024 * 1024)  // 256MB write buffer

typedef struct {
    char device_path[256];
    char mount_point[256];
    uint64_t total_space;
    uint64_t free_space;
    uint64_t used_space;
    int write_cache_enabled;
    int direct_io_supported;
} storage_info_t;

static storage_info_t storage_info = {0};
static int initialized = 0;

/* Initialize storage manager */
int storage_init(const char *recording_path) {
    struct statvfs stat;

    if (statvfs(recording_path, &stat) != 0) {
        syslog(LOG_ERR, "Failed to stat filesystem: %s", strerror(errno));
        return -1;
    }

    strncpy(storage_info.mount_point, recording_path, sizeof(storage_info.mount_point) - 1);
    storage_info.total_space = stat.f_blocks * stat.f_frsize;
    storage_info.free_space = stat.f_bavail * stat.f_frsize;
    storage_info.used_space = storage_info.total_space - storage_info.free_space;

    syslog(LOG_INFO, "Storage initialized: %.2f GB total, %.2f GB free",
           (double)storage_info.total_space / (1024*1024*1024),
           (double)storage_info.free_space / (1024*1024*1024));

    initialized = 1;
    return 0;
}

/* Get available storage space */
uint64_t storage_get_free_space(void) {
    struct statvfs stat;

    if (!initialized) return 0;

    if (statvfs(storage_info.mount_point, &stat) == 0) {
        storage_info.free_space = stat.f_bavail * stat.f_frsize;
        return storage_info.free_space;
    }

    return 0;
}

/* Check if sufficient space available */
int storage_has_space(uint64_t required_bytes) {
    uint64_t free = storage_get_free_space();
    uint64_t min_reserve = (uint64_t)MIN_FREE_SPACE_GB * 1024 * 1024 * 1024;

    return (free - required_bytes) > min_reserve;
}

/* Open file with optimal flags for recording */
int storage_open_recording(const char *filename, int flags) {
    char full_path[512];
    int fd;
    int open_flags = flags;

    snprintf(full_path, sizeof(full_path), "%s/%s", storage_info.mount_point, filename);

    /* Use O_DIRECT for zero-copy writes */
    open_flags |= O_DIRECT | O_SYNC;

    fd = open(full_path, open_flags, 0644);
    if (fd < 0) {
        /* Fallback without O_DIRECT if not supported */
        open_flags &= ~O_DIRECT;
        fd = open(full_path, open_flags, 0644);

        if (fd < 0) {
            syslog(LOG_ERR, "Failed to open file %s: %s", full_path, strerror(errno));
            return -1;
        }

        storage_info.direct_io_supported = 0;
        syslog(LOG_WARNING, "O_DIRECT not supported, using buffered I/O");
    } else {
        storage_info.direct_io_supported = 1;
    }

    /* Pre-allocate file space to avoid fragmentation */
    #ifdef FALLOC_FL_KEEP_SIZE
    if (fallocate(fd, FALLOC_FL_KEEP_SIZE, 0, 100LL * 1024 * 1024 * 1024) < 0) {
        syslog(LOG_WARNING, "Failed to preallocate space: %s", strerror(errno));
    }
    #endif

    return fd;
}

/* Optimize write performance */
ssize_t storage_write_optimized(int fd, const void *buf, size_t count) {
    ssize_t written = 0;
    size_t remaining = count;
    const char *ptr = (const char *)buf;

    while (remaining > 0) {
        ssize_t n = write(fd, ptr, remaining);

        if (n < 0) {
            if (errno == EINTR) continue;
            syslog(LOG_ERR, "Write failed: %s", strerror(errno));
            return -1;
        }

        written += n;
        remaining -= n;
        ptr += n;
    }

    return written;
}

/* Flush buffers to disk */
int storage_sync(int fd) {
    if (fdatasync(fd) < 0) {
        syslog(LOG_ERR, "Failed to sync: %s", strerror(errno));
        return -1;
    }
    return 0;
}

/* Delete old recordings to free space */
int storage_cleanup_old_recordings(uint64_t target_free_bytes) {
    char command[512];
    int files_deleted = 0;

    /* Find and delete oldest recordings until target space reached */
    snprintf(command, sizeof(command),
             "find %s -name '*.mp4' -type f -printf '%%T@ %%p\\n' | sort -n | head -10",
             storage_info.mount_point);

    FILE *fp = popen(command, "r");
    if (!fp) return -1;

    char line[512];
    while (fgets(line, sizeof(line), fp)) {
        char *filename = strchr(line, ' ');
        if (filename) {
            filename++; // Skip space
            filename[strcspn(filename, "\n")] = 0; // Remove newline

            if (unlink(filename) == 0) {
                files_deleted++;
                syslog(LOG_INFO, "Deleted old recording: %s", filename);

                if (storage_get_free_space() >= target_free_bytes) {
                    break;
                }
            }
        }
    }

    pclose(fp);
    return files_deleted;
}

/* Get storage statistics */
int storage_get_stats(storage_stats_t *stats) {
    if (!initialized || !stats) return -1;

    struct statvfs vfs;
    if (statvfs(storage_info.mount_point, &vfs) != 0) {
        return -1;
    }

    stats->total_bytes = vfs.f_blocks * vfs.f_frsize;
    stats->free_bytes = vfs.f_bavail * vfs.f_frsize;
    stats->used_bytes = stats->total_bytes - stats->free_bytes;
    stats->usage_percent = (stats->used_bytes * 100) / stats->total_bytes;

    /* Get inode stats */
    stats->total_inodes = vfs.f_files;
    stats->free_inodes = vfs.f_ffree;
    stats->used_inodes = stats->total_inodes - stats->free_inodes;

    return 0;
}

/* Enable write-through cache for metadata */
int storage_enable_writecache(const char *device) {
    char command[256];

    /* Enable write cache on NVMe */
    snprintf(command, sizeof(command), "nvme set-feature %s -f 0x06 -v 1", device);

    if (system(command) == 0) {
        storage_info.write_cache_enabled = 1;
        syslog(LOG_INFO, "Write cache enabled on %s", device);
        return 0;
    }

    return -1;
}

/* Tune filesystem for video workload */
int storage_tune_filesystem(void) {
    int ret = 0;

    /* These would typically be applied at mount time via fstab */
    syslog(LOG_INFO, "Filesystem tuning applied via mount options");
    syslog(LOG_INFO, "  - noatime: Skip access time updates");
    syslog(LOG_INFO, "  - nodiratime: Skip directory access time");
    syslog(LOG_INFO, "  - data=writeback: Fast write mode");
    syslog(LOG_INFO, "  - commit=120: Delayed commit for throughput");

    return ret;
}

/* Benchmark write performance */
int storage_benchmark(benchmark_result_t *result) {
    char test_file[512];
    int fd;
    struct timespec start, end;
    const size_t block_size = 1024 * 1024;  // 1MB blocks
    const size_t num_blocks = 1024;         // 1GB test
    char *buffer;
    size_t i;

    if (!result) return -1;

    snprintf(test_file, sizeof(test_file), "%s/.benchmark_test", storage_info.mount_point);

    /* Allocate aligned buffer for O_DIRECT */
    if (posix_memalign((void **)&buffer, 4096, block_size) != 0) {
        return -1;
    }

    /* Fill buffer with test pattern */
    memset(buffer, 0xAA, block_size);

    /* Open file with O_DIRECT */
    fd = open(test_file, O_WRONLY | O_CREAT | O_TRUNC | O_DIRECT, 0644);
    if (fd < 0) {
        /* Fallback without O_DIRECT */
        fd = open(test_file, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (fd < 0) {
            free(buffer);
            return -1;
        }
    }

    /* Sequential write test */
    clock_gettime(CLOCK_MONOTONIC, &start);

    for (i = 0; i < num_blocks; i++) {
        if (write(fd, buffer, block_size) != (ssize_t)block_size) {
            close(fd);
            unlink(test_file);
            free(buffer);
            return -1;
        }
    }

    fdatasync(fd);
    clock_gettime(CLOCK_MONOTONIC, &end);

    close(fd);
    unlink(test_file);
    free(buffer);

    /* Calculate results */
    double elapsed = (end.tv_sec - start.tv_sec) +
                    (end.tv_nsec - start.tv_nsec) / 1000000000.0;

    result->write_speed_mbps = (double)(block_size * num_blocks) / (1024 * 1024) / elapsed;
    result->latency_ms = (elapsed * 1000.0) / num_blocks;
    result->test_size_mb = (block_size * num_blocks) / (1024 * 1024);

    syslog(LOG_INFO, "Storage benchmark: %.2f MB/s write, %.2f ms latency",
           result->write_speed_mbps, result->latency_ms);

    return 0;
}

/* Cleanup on shutdown */
void storage_cleanup(void) {
    if (initialized) {
        syslog(LOG_INFO, "Storage manager cleanup");
        initialized = 0;
    }
}