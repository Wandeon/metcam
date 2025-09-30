cmake_minimum_required(VERSION 3.18)
project(metcam_processing LANGUAGES CXX CUDA)

# C++17 and CUDA 17
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)

# CUDA architecture (Jetson Orin: compute capability 8.7)
set(CMAKE_CUDA_ARCHITECTURES 87)

# Find required packages
find_package(CUDA 12.0 REQUIRED)
find_package(OpenCV 4.8 REQUIRED)
find_package(Python3 COMPONENTS Interpreter Development REQUIRED)

# Try to find pybind11
find_package(pybind11 CONFIG)
if(NOT pybind11_FOUND)
    message(STATUS "pybind11 not found, attempting to download...")
    include(FetchContent)
    FetchContent_Declare(
        pybind11
        GIT_REPOSITORY https://github.com/pybind/pybind11
        GIT_TAG v2.11.1
    )
    FetchContent_MakeAvailable(pybind11)
endif()

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CUDA_INCLUDE_DIRS}
    ${OpenCV_INCLUDE_DIRS}
    ${Python3_INCLUDE_DIRS}
)

# CUDA flags
set(CMAKE_CUDA_FLAGS "${CMAKE_CUDA_FLAGS} --use_fast_math -Xcompiler -fPIC")
set(CMAKE_CUDA_FLAGS_RELEASE "${CMAKE_CUDA_FLAGS_RELEASE} -O3")

# Components
add_subdirectory(architecture)
add_subdirectory(calibration)
add_subdirectory(barrel-correction)
add_subdirectory(panoramic-stitcher)
add_subdirectory(color-matching)
add_subdirectory(gpu-memory)
add_subdirectory(video-codec)
add_subdirectory(optimization)
add_subdirectory(quality-metrics)
add_subdirectory(batch-manager)

# Install Python modules
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/
    DESTINATION ${CMAKE_INSTALL_PREFIX}/python/processing
    FILES_MATCHING PATTERN "*.py"
    PATTERN "__pycache__" EXCLUDE
    PATTERN "build" EXCLUDE
    PATTERN "tests" EXCLUDE
    PATTERN "benchmarks" EXCLUDE
)

# Install headers
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/
    DESTINATION ${CMAKE_INSTALL_PREFIX}/include/processing
    FILES_MATCHING PATTERN "*.h" PATTERN "*.cuh"
)

# Print configuration
message(STATUS "")
message(STATUS "=== FootballVision Pro Processing Pipeline Configuration ===")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "CUDA version: ${CUDA_VERSION}")
message(STATUS "CUDA architectures: ${CMAKE_CUDA_ARCHITECTURES}")
message(STATUS "OpenCV version: ${OpenCV_VERSION}")
message(STATUS "Python version: ${Python3_VERSION}")
message(STATUS "Install prefix: ${CMAKE_INSTALL_PREFIX}")
message(STATUS "=============================================================")
message(STATUS "")