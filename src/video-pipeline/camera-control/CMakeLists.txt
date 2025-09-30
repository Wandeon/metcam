cmake_minimum_required(VERSION 3.16)
project(CameraControl)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../pipeline-architecture/include
)

# In production, link against libargus
# find_package(Argus REQUIRED)

# Camera control library
add_library(camera_control OBJECT
    src/camera_control.cpp
)

# For production Jetson builds:
# target_link_libraries(camera_control
#     argus
#     nvbuf_utils
# )

# Tests
add_executable(test_camera_control
    tests/test_camera_control.cpp
)

target_link_libraries(test_camera_control
    camera_control
)

# Install
install(TARGETS test_camera_control
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
    FILES_MATCHING PATTERN "*.h"
)