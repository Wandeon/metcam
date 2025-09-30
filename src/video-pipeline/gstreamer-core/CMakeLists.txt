cmake_minimum_required(VERSION 3.16)
project(GStreamerCore)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../pipeline-architecture/include
)

# In production: Find GStreamer
# find_package(PkgConfig REQUIRED)
# pkg_check_modules(GSTREAMER REQUIRED gstreamer-1.0)
# pkg_check_modules(GSTREAMER_VIDEO REQUIRED gstreamer-video-1.0)
# include_directories(${GSTREAMER_INCLUDE_DIRS})

# GStreamer core library
add_library(gstreamer_core OBJECT
    src/gstreamer_pipeline.cpp
    src/nvmm_buffer_manager.cpp
)

# For production:
# target_link_libraries(gstreamer_core
#     ${GSTREAMER_LIBRARIES}
#     nvbufsurface
#     nvbuf_utils
# )

# Tests
add_executable(test_gstreamer_core
    tests/test_pipeline.cpp
)

target_link_libraries(test_gstreamer_core
    gstreamer_core
)

# Install
install(TARGETS test_gstreamer_core
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
    FILES_MATCHING PATTERN "*.h"
)