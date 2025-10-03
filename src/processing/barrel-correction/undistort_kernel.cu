/**
 * W23: CUDA Barrel Distortion Correction Kernel
 * Target: 125 FPS @ 4056×3040 (IMX477 full resolution)
 *
 * Applies inverse barrel distortion using Brown-Conrady model:
 * x_corrected = x_distorted * (1 + k1*r² + k2*r⁴ + k3*r⁶)
 */

#include <cuda_runtime.h>
#include <stdio.h>

/**
 * CUDA kernel for barrel distortion correction
 * Each thread processes one pixel
 */
__global__ void undistort_kernel(
    const unsigned char* __restrict__ input,
    unsigned char* __restrict__ output,
    int width, int height,
    float k1, float k2, float k3,  // Radial distortion coefficients
    float cx, float cy,             // Principal point (image center)
    float fx, float fy              // Focal length in pixels
) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;

    if (x >= width || y >= height) return;

    // Normalize coordinates to [-1, 1] range
    float xn = (x - cx) / fx;
    float yn = (y - cy) / fy;

    // Calculate radial distance squared
    float r2 = xn*xn + yn*yn;
    float r4 = r2 * r2;
    float r6 = r4 * r2;

    // Apply Brown-Conrady distortion model (inverse)
    float radial_distortion = 1.0f + k1*r2 + k2*r4 + k3*r6;

    // Distort coordinates
    float xu = xn * radial_distortion;
    float yu = yn * radial_distortion;

    // Denormalize back to pixel coordinates
    int src_x = (int)(xu * fx + cx);
    int src_y = (int)(yu * fy + cy);

    // Bounds check with clamping
    src_x = max(0, min(src_x, width - 1));
    src_y = max(0, min(src_y, height - 1));

    // Copy RGB pixel (3 bytes per pixel)
    int dst_idx = (y * width + x) * 3;
    int src_idx = (src_y * width + src_x) * 3;

    output[dst_idx + 0] = input[src_idx + 0];  // R
    output[dst_idx + 1] = input[src_idx + 1];  // G
    output[dst_idx + 2] = input[src_idx + 2];  // B
}

/**
 * Host function to launch undistortion kernel
 * Processes a single RGB frame
 */
extern "C" {
    void undistort_frame(
        const unsigned char* h_input,
        unsigned char* h_output,
        int width, int height,
        float k1, float k2, float k3,
        float cx, float cy, float fx, float fy
    ) {
        // Allocate device memory
        unsigned char *d_input, *d_output;
        size_t image_size = width * height * 3;  // RGB

        cudaMalloc(&d_input, image_size);
        cudaMalloc(&d_output, image_size);

        // Copy input frame to device
        cudaMemcpy(d_input, h_input, image_size, cudaMemcpyHostToDevice);

        // Configure kernel launch parameters
        // 16x16 threads per block is optimal for most GPUs
        dim3 block(16, 16);
        dim3 grid(
            (width + block.x - 1) / block.x,
            (height + block.y - 1) / block.y
        );

        // Launch kernel
        undistort_kernel<<<grid, block>>>(
            d_input, d_output, width, height,
            k1, k2, k3, cx, cy, fx, fy
        );

        // Wait for kernel to complete
        cudaDeviceSynchronize();

        // Copy result back to host
        cudaMemcpy(h_output, d_output, image_size, cudaMemcpyDeviceToHost);

        // Cleanup device memory
        cudaFree(d_input);
        cudaFree(d_output);
    }

    /**
     * Batch processing version for multiple frames
     * More efficient for video processing
     */
    void undistort_batch(
        const unsigned char** h_inputs,
        unsigned char** h_outputs,
        int num_frames,
        int width, int height,
        float k1, float k2, float k3,
        float cx, float cy, float fx, float fy
    ) {
        size_t frame_size = width * height * 3;

        // Allocate device memory for batch
        unsigned char *d_input, *d_output;
        cudaMalloc(&d_input, frame_size * num_frames);
        cudaMalloc(&d_output, frame_size * num_frames);

        // Copy all frames to device
        for (int i = 0; i < num_frames; i++) {
            cudaMemcpy(
                d_input + i * frame_size,
                h_inputs[i],
                frame_size,
                cudaMemcpyHostToDevice
            );
        }

        // Launch kernel for each frame
        dim3 block(16, 16);
        dim3 grid(
            (width + block.x - 1) / block.x,
            (height + block.y - 1) / block.y
        );

        for (int i = 0; i < num_frames; i++) {
            undistort_kernel<<<grid, block>>>(
                d_input + i * frame_size,
                d_output + i * frame_size,
                width, height,
                k1, k2, k3, cx, cy, fx, fy
            );
        }

        cudaDeviceSynchronize();

        // Copy all frames back to host
        for (int i = 0; i < num_frames; i++) {
            cudaMemcpy(
                h_outputs[i],
                d_output + i * frame_size,
                frame_size,
                cudaMemcpyDeviceToHost
            );
        }

        // Cleanup
        cudaFree(d_input);
        cudaFree(d_output);
    }
}
