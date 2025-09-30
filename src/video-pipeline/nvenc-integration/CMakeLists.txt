cmake_minimum_required(VERSION 3.16)
project(NVENCIntegration)

set(CMAKE_CXX_STANDARD 17)

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../pipeline-architecture/include
)

add_library(nvenc_integration OBJECT
    src/nvenc_encoder.cpp
)

# Production: link nvenc library
# target_link_libraries(nvenc_integration nvenc)