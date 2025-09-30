cmake_minimum_required(VERSION 3.16)
project(PreviewPipeline)

set(CMAKE_CXX_STANDARD 17)

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../pipeline-architecture/include
)

add_library(preview_pipeline OBJECT
    src/preview_pipeline.cpp
)