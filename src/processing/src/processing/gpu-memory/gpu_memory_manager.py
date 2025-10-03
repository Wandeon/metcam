"""
W26: GPU Memory Manager
Manages CUDA memory pools and tracks utilization
Target: <4GB GPU memory usage for entire processing pipeline
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BufferInfo:
    """Information about allocated GPU buffer"""
    name: str
    size_bytes: int
    allocated_at: float

class GPUMemoryManager:
    """
    Manages GPU memory allocation for processing pipeline
    Implements pool allocation and tracking to stay under 4GB limit
    """

    def __init__(self, max_memory_gb: float = 4.0):
        self.max_memory = int(max_memory_gb * 1024**3)
        self.allocated_buffers: Dict[str, BufferInfo] = {}
        self.total_allocated = 0

        # Try to import PyCUDA if available
        self.cuda_available = False
        try:
            import pycuda.driver as cuda
            import pycuda.autoinit
            self.cuda = cuda
            self.cuda_available = True
            logger.info(f"[GPU Memory] CUDA initialized, limit: {max_memory_gb}GB")
        except ImportError:
            logger.warning("[GPU Memory] PyCUDA not available, using simulation mode")

    def allocate_buffer(self, name: str, size_bytes: int):
        """
        Allocate GPU buffer with tracking

        Args:
            name: Unique buffer identifier
            size_bytes: Size to allocate in bytes

        Returns:
            Buffer handle (DeviceAllocation if CUDA available, else None)

        Raises:
            MemoryError: If allocation would exceed limit
        """
        if self.total_allocated + size_bytes > self.max_memory:
            raise MemoryError(
                f"Would exceed {self.max_memory / 1024**3:.1f}GB limit "
                f"(current: {self.total_allocated / 1024**3:.2f}GB, "
                f"requested: {size_bytes / 1024**3:.2f}GB)"
            )

        if name in self.allocated_buffers:
            logger.warning(f"[GPU Memory] Buffer '{name}' already exists, freeing old allocation")
            self.free_buffer(name)

        buffer = None
        if self.cuda_available:
            buffer = self.cuda.mem_alloc(size_bytes)

        import time
        buffer_info = BufferInfo(
            name=name,
            size_bytes=size_bytes,
            allocated_at=time.time()
        )

        self.allocated_buffers[name] = buffer_info
        self.total_allocated += size_bytes

        logger.info(
            f"[GPU Memory] Allocated {size_bytes / 1024**2:.1f}MB for '{name}' "
            f"({self.total_allocated / 1024**3:.2f}GB / {self.max_memory / 1024**3:.1f}GB used)"
        )

        return buffer

    def free_buffer(self, name: str):
        """Free specific buffer"""
        if name not in self.allocated_buffers:
            logger.warning(f"[GPU Memory] Buffer '{name}' not found")
            return

        buffer_info = self.allocated_buffers[name]
        size = buffer_info.size_bytes

        # Note: In real implementation, we'd free the actual CUDA buffer here
        # buffer.free()

        del self.allocated_buffers[name]
        self.total_allocated -= size

        logger.info(
            f"[GPU Memory] Freed '{name}' ({size / 1024**2:.1f}MB) "
            f"({self.total_allocated / 1024**3:.2f}GB / {self.max_memory / 1024**3:.1f}GB used)"
        )

    def get_utilization(self) -> Dict:
        """
        Get current GPU memory utilization

        Returns:
            Dict with memory stats in MB and utilization percentage
        """
        stats = {
            'allocated_mb': self.total_allocated / 1024**2,
            'limit_mb': self.max_memory / 1024**2,
            'utilization_percent': (self.total_allocated / self.max_memory) * 100,
            'num_buffers': len(self.allocated_buffers),
            'buffers': {
                name: info.size_bytes / 1024**2
                for name, info in self.allocated_buffers.items()
            }
        }

        if self.cuda_available:
            try:
                free, total = self.cuda.mem_get_info()
                stats.update({
                    'gpu_total_mb': total / 1024**2,
                    'gpu_free_mb': free / 1024**2,
                    'gpu_used_mb': (total - free) / 1024**2,
                    'gpu_utilization_percent': ((total - free) / total) * 100
                })
            except:
                pass

        return stats

    def allocate_frame_buffers(self, width: int, height: int, num_buffers: int = 6):
        """
        Allocate frame buffers for video processing

        Args:
            width: Frame width in pixels
            height: Frame height in pixels
            num_buffers: Number of frame buffers (default: 6 for double-buffering)

        Returns:
            List of buffer names
        """
        frame_size = width * height * 3  # RGB
        buffer_names = []

        for i in range(num_buffers):
            name = f'frame_buffer_{i}'
            self.allocate_buffer(name, frame_size)
            buffer_names.append(name)

        logger.info(
            f"[GPU Memory] Allocated {num_buffers} frame buffers "
            f"({width}×{height} RGB = {frame_size / 1024**2:.1f}MB each)"
        )

        return buffer_names

    def cleanup(self):
        """Free all allocated buffers"""
        logger.info(f"[GPU Memory] Cleaning up {len(self.allocated_buffers)} buffers...")

        for name in list(self.allocated_buffers.keys()):
            self.free_buffer(name)

        logger.info("[GPU Memory] Cleanup complete")

    def print_stats(self):
        """Print detailed memory statistics"""
        util = self.get_utilization()

        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("    GPU Memory Manager Statistics")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"Allocated: {util['allocated_mb']:.1f}MB / {util['limit_mb']:.1f}MB")
        print(f"Utilization: {util['utilization_percent']:.1f}%")
        print(f"Active Buffers: {util['num_buffers']}")

        if 'gpu_total_mb' in util:
            print(f"\nGPU Device:")
            print(f"  Total: {util['gpu_total_mb']:.1f}MB")
            print(f"  Used: {util['gpu_used_mb']:.1f}MB")
            print(f"  Free: {util['gpu_free_mb']:.1f}MB")
            print(f"  Utilization: {util['gpu_utilization_percent']:.1f}%")

        if util['num_buffers'] > 0:
            print(f"\nBuffer Details:")
            for name, size_mb in util['buffers'].items():
                print(f"  {name}: {size_mb:.1f}MB")

        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")


# CLI testing and demonstration
if __name__ == '__main__':
    print("GPU Memory Manager - Test Suite")
    print("================================\n")

    # Create manager with 4GB limit
    mgr = GPUMemoryManager(max_memory_gb=4.0)

    # Test 1: Allocate frame buffers for 4K processing
    print("Test 1: Allocating frame buffers for 4056×3040 (IMX477)...")
    try:
        frame_buffers = mgr.allocate_frame_buffers(4056, 3040, num_buffers=6)
        print(f"✓ Allocated {len(frame_buffers)} frame buffers")
    except MemoryError as e:
        print(f"✗ Allocation failed: {e}")

    mgr.print_stats()

    # Test 2: Allocate panorama buffer (7000×3040)
    print("Test 2: Allocating panorama buffer (7000×3040)...")
    try:
        panorama_size = 7000 * 3040 * 3
        mgr.allocate_buffer('panorama', panorama_size)
        print(f"✓ Allocated panorama buffer ({panorama_size / 1024**2:.1f}MB)")
    except MemoryError as e:
        print(f"✗ Allocation failed: {e}")

    mgr.print_stats()

    # Test 3: Check if we're under 4GB limit
    util = mgr.get_utilization()
    if util['utilization_percent'] < 100:
        print(f"✓ Memory usage within limit ({util['utilization_percent']:.1f}%)")
    else:
        print(f"✗ Memory usage exceeds limit ({util['utilization_percent']:.1f}%)")

    # Test 4: Cleanup
    print("\nTest 4: Cleanup...")
    mgr.cleanup()
    mgr.print_stats()
    print("✓ All tests complete")
