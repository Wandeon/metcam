# Makefile for CUDA barrel correction kernel

NVCC = nvcc
CUDA_ARCH = sm_87  # Jetson Orin Nano architecture

# Compiler flags
NVCCFLAGS = -O3 -arch=$(CUDA_ARCH) -Xcompiler -fPIC

# Targets
all: libundistort.so

libundistort.so: undistort_kernel.cu
	$(NVCC) $(NVCCFLAGS) -shared undistort_kernel.cu -o libundistort.so

clean:
	rm -f libundistort.so

test: libundistort.so
	@echo "Library compiled successfully"
	@echo "Target: 125 FPS @ 4056×3040"
	@echo "Use: LD_LIBRARY_PATH=. python test_undistort.py"

.PHONY: all clean test
