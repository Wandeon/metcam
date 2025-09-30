/*
 * Storage Manager Header
 * Public API for storage optimization
 */

#ifndef STORAGE_MANAGER_H
#define STORAGE_MANAGER_H

#include <stdint.h>
#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Storage statistics structure */
typedef struct {
    uint64_t total_bytes;
    uint64_t free_bytes;
    uint64_t used_bytes;
    uint32_t usage_percent;
    uint64_t total_inodes;
    uint64_t free_inodes;
    uint64_t used_inodes;
} storage_stats_t;

/* Benchmark results */
typedef struct {
    double write_speed_mbps;
    double read_speed_mbps;
    double latency_ms;
    uint32_t test_size_mb;
} benchmark_result_t;

/**
 * Initialize storage manager
 * @param recording_path Path to recording storage directory
 * @return 0 on success, -1 on error
 */
int storage_init(const char *recording_path);

/**
 * Get available free space
 * @return Free space in bytes
 */
uint64_t storage_get_free_space(void);

/**
 * Check if sufficient space available for recording
 * @param required_bytes Required space in bytes
 * @return 1 if space available, 0 otherwise
 */
int storage_has_space(uint64_t required_bytes);

/**
 * Open file optimized for video recording
 * @param filename File name (relative to recording path)
 * @param flags Additional open flags
 * @return File descriptor on success, -1 on error
 */
int storage_open_recording(const char *filename, int flags);

/**
 * Write data with optimizations
 * @param fd File descriptor
 * @param buf Data buffer
 * @param count Number of bytes to write
 * @return Number of bytes written, -1 on error
 */
ssize_t storage_write_optimized(int fd, const void *buf, size_t count);

/**
 * Sync buffers to disk
 * @param fd File descriptor
 * @return 0 on success, -1 on error
 */
int storage_sync(int fd);

/**
 * Delete old recordings to free space
 * @param target_free_bytes Target free space in bytes
 * @return Number of files deleted, -1 on error
 */
int storage_cleanup_old_recordings(uint64_t target_free_bytes);

/**
 * Get storage statistics
 * @param stats Pointer to stats structure
 * @return 0 on success, -1 on error
 */
int storage_get_stats(storage_stats_t *stats);

/**
 * Enable write cache on device
 * @param device Device path (e.g., /dev/nvme0n1)
 * @return 0 on success, -1 on error
 */
int storage_enable_writecache(const char *device);

/**
 * Tune filesystem for video workload
 * @return 0 on success, -1 on error
 */
int storage_tune_filesystem(void);

/**
 * Benchmark storage performance
 * @param result Pointer to result structure
 * @return 0 on success, -1 on error
 */
int storage_benchmark(benchmark_result_t *result);

/**
 * Cleanup storage manager
 */
void storage_cleanup(void);

#ifdef __cplusplus
}
#endif

#endif /* STORAGE_MANAGER_H */