cmake_minimum_required(VERSION 3.10)

project(tocGPT C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

file(GLOB SRC_FILES "${CMAKE_SOURCE_DIR}/src/*.c")

add_executable(toc_server ${SRC_FILES})

target_include_directories(toc_server PRIVATE "${CMAKE_SOURCE_DIR}/src")

target_link_libraries(toc_server PRIVATE crypt m)

set_target_properties(toc_server PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}"
)
