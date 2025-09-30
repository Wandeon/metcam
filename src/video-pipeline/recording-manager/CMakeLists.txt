cmake_minimum_required(VERSION 3.16)
project(RecordingManager)

set(CMAKE_CXX_STANDARD 17)

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../pipeline-architecture/include
)

add_library(recording_manager OBJECT
    src/recording_manager.cpp
)