cmake_minimum_required(VERSION 3.16)
project(PipelineMonitor)

set(CMAKE_CXX_STANDARD 17)

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../pipeline-architecture/include
)

add_library(pipeline_monitor OBJECT
    src/pipeline_monitor.cpp
)