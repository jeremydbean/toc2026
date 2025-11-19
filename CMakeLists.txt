cmake_minimum_required(VERSION 3.20)

project(TOC2026 LANGUAGES C)

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

set(TARGET_NAME rom)

# Include all source files, including the new string_safe.c
file(GLOB SRC_FILES CONFIGURE_DEPENDS "${CMAKE_SOURCE_DIR}/src/*.c")

add_executable(${TARGET_NAME} ${SRC_FILES})

target_include_directories(${TARGET_NAME} PRIVATE "${CMAKE_SOURCE_DIR}/src")

target_compile_definitions(${TARGET_NAME} PRIVATE ROM)

target_compile_options(
    ${TARGET_NAME}
    PRIVATE
        -Wall
        -Wextra
        -Wpedantic
        -Wno-unused-parameter
        -Wno-sign-compare
        -Wno-strict-aliasing
)

# Link against math (m), compression (z), and crypto (crypt)
target_link_libraries(${TARGET_NAME} PRIVATE m z crypt)
