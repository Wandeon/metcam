cmake_minimum_required(VERSION 3.16)
project(FootballVisionArchitecture)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Export include directory for other components
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# Install headers
install(
    DIRECTORY include/footballvision
    DESTINATION include
    FILES_MATCHING PATTERN "*.h"
)

# Architecture is header-only, no library to build
add_custom_target(architecture-headers ALL
    COMMENT "Football Vision architecture headers"
)