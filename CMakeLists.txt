cmake_minimum_required(VERSION 3.20)

project(TOC2026 LANGUAGES C)

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

set(TARGET_NAME rom)

# Place build outputs in dedicated directories.
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/bin")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/obj")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/obj")

# Mirror the output directories for multi-config generators.
if(CMAKE_CONFIGURATION_TYPES)
    foreach(OUTPUTCONFIG IN LISTS CMAKE_CONFIGURATION_TYPES)
        string(TOUPPER "${OUTPUTCONFIG}" OUTPUTCONFIG_UPPER)
        set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_${OUTPUTCONFIG_UPPER} "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}")
        set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_${OUTPUTCONFIG_UPPER} "${CMAKE_ARCHIVE_OUTPUT_DIRECTORY}")
        set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_${OUTPUTCONFIG_UPPER} "${CMAKE_LIBRARY_OUTPUT_DIRECTORY}")
    endforeach()
endif()

# Explicitly list all source files to avoid globbing.
set(SRC_FILES
    src/act_comm.c
    src/act_info.c
    src/act_move.c
    src/act_obj.c
    src/act_wiz.c
    src/color.c
    src/comm.c
    src/const.c
    src/container.c
    src/db.c
    src/dstring.c
    src/edit.c
    src/fight.c
    src/handler.c
    src/hunt.c
    src/interp.c
    src/list.c
    src/magic.c
    src/magic2.c
    src/maxload.c
    src/misc.c
    src/pkill.c
    src/quest.c
    src/save.c
    src/skills.c
    src/script_event.c
    src/special.c
    src/string_safe.c
    src/stubs.c
    src/update.c
    src/wizlist.c
)

add_executable(${TARGET_NAME})
target_sources(${TARGET_NAME} PRIVATE ${SRC_FILES})

target_include_directories(${TARGET_NAME} PRIVATE "${CMAKE_SOURCE_DIR}/src")

target_compile_definitions(${TARGET_NAME} PRIVATE ROM)

option(ENABLE_SANITIZERS "Enable address and undefined sanitizers for debug validation" OFF)

set(SANITIZER_FLAGS
    -fsanitize=address
    -fsanitize=undefined
)

target_compile_options(
    ${TARGET_NAME}
    PRIVATE
        -Wall
        -Wextra
        -Wpedantic
        -Werror=implicit-function-declaration
        -Wno-unused-parameter
        -Wno-sign-compare
        -Wno-strict-aliasing
        $<$<AND:$<BOOL:${ENABLE_SANITIZERS}>,$<CONFIG:Debug>>:${SANITIZER_FLAGS}>
)

target_link_options(
    ${TARGET_NAME}
    PRIVATE
        $<$<AND:$<BOOL:${ENABLE_SANITIZERS}>,$<CONFIG:Debug>>:${SANITIZER_FLAGS}>
)

# Link against math (m), compression (z), and crypto (crypt)
target_link_libraries(${TARGET_NAME} PRIVATE m z crypt)
