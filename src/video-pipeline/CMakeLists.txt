cmake_minimum_required(VERSION 3.16)
project(FootballVisionPipeline VERSION 1.0.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native -fPIC")
set(CMAKE_CXX_FLAGS_DEBUG "-g -O0 -fPIC")
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Project-wide include
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/pipeline-architecture/include
    ${CMAKE_CURRENT_SOURCE_DIR}/camera-control/include
    ${CMAKE_CURRENT_SOURCE_DIR}/gstreamer-core/include
    ${CMAKE_CURRENT_SOURCE_DIR}/nvenc-integration/include
    ${CMAKE_CURRENT_SOURCE_DIR}/recording-manager/include
    ${CMAKE_CURRENT_SOURCE_DIR}/stream-sync/include
    ${CMAKE_CURRENT_SOURCE_DIR}/preview-pipeline/include
    ${CMAKE_CURRENT_SOURCE_DIR}/pipeline-monitor/include
    ${CMAKE_CURRENT_SOURCE_DIR}/storage-writer/include
    ${CMAKE_CURRENT_SOURCE_DIR}/recovery-system/include
)

# Add all component subdirectories
add_subdirectory(pipeline-architecture)
add_subdirectory(camera-control)
add_subdirectory(gstreamer-core)
add_subdirectory(nvenc-integration)
add_subdirectory(recording-manager)
add_subdirectory(stream-sync)
add_subdirectory(preview-pipeline)
add_subdirectory(pipeline-monitor)
add_subdirectory(storage-writer)
add_subdirectory(recovery-system)

# Main library combining all components
add_library(footballvision SHARED
    $<TARGET_OBJECTS:camera_control>
    $<TARGET_OBJECTS:gstreamer_core>
    $<TARGET_OBJECTS:nvenc_integration>
    $<TARGET_OBJECTS:recording_manager>
    $<TARGET_OBJECTS:stream_sync>
    $<TARGET_OBJECTS:preview_pipeline>
    $<TARGET_OBJECTS:pipeline_monitor>
    $<TARGET_OBJECTS:storage_writer>
    $<TARGET_OBJECTS:recovery_system>
)

set_target_properties(footballvision PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
)

# Main executable
add_executable(footballvision-recorder
    main/recorder_main.cpp
)

target_link_libraries(footballvision-recorder
    footballvision
    pthread
)

# Install targets
install(TARGETS footballvision footballvision-recorder
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY pipeline-architecture/include/footballvision
    DESTINATION include
    FILES_MATCHING PATTERN "*.h"
)

# Testing
enable_testing()

# Package configuration
set(CPACK_PROJECT_NAME ${PROJECT_NAME})
set(CPACK_PROJECT_VERSION ${PROJECT_VERSION})
include(CPack)

# Print configuration
message(STATUS "")
message(STATUS "FootballVision Pipeline Configuration:")
message(STATUS "  Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "  C++ standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "  Install prefix: ${CMAKE_INSTALL_PREFIX}")
message(STATUS "")