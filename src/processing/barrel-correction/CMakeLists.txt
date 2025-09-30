cmake_minimum_required(VERSION 3.18)

# CUDA undistortion kernel
add_library(barrel_correction_cuda SHARED
    cuda/undistort_kernel.cu
)

target_link_libraries(barrel_correction_cuda
    ${CUDA_LIBRARIES}
    ${OpenCV_LIBS}
)

set_target_properties(barrel_correction_cuda PROPERTIES
    CUDA_SEPARABLE_COMPILATION ON
    POSITION_INDEPENDENT_CODE ON
)

# Install
install(TARGETS barrel_correction_cuda
    LIBRARY DESTINATION ${CMAKE_INSTALL_PREFIX}/lib
)