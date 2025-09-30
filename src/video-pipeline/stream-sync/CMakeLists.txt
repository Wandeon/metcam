cmake_minimum_required(VERSION 3.16)
project(StreamSync)

set(CMAKE_CXX_STANDARD 17)

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../pipeline-architecture/include
)

add_library(stream_sync OBJECT
    src/stream_sync.cpp
)