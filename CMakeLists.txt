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
    "${CMAKE_SOURCE_DIR}/src/act_comm.c"
    "${CMAKE_SOURCE_DIR}/src/act_info.c"
    "${CMAKE_SOURCE_DIR}/src/act_move.c"
    "${CMAKE_SOURCE_DIR}/src/act_obj.c"
    "${CMAKE_SOURCE_DIR}/src/act_wiz.c"
    "${CMAKE_SOURCE_DIR}/src/comm.c"
    "${CMAKE_SOURCE_DIR}/src/const.c"
    "${CMAKE_SOURCE_DIR}/src/db.c"
    "${CMAKE_SOURCE_DIR}/src/edit.c"
    "${CMAKE_SOURCE_DIR}/src/fight.c"
    "${CMAKE_SOURCE_DIR}/src/handler.c"
    "${CMAKE_SOURCE_DIR}/src/hunt.c"
    "${CMAKE_SOURCE_DIR}/src/interp.c"
    "${CMAKE_SOURCE_DIR}/src/magic.c"
    "${CMAKE_SOURCE_DIR}/src/magic2.c"
    "${CMAKE_SOURCE_DIR}/src/maxload.c"
    "${CMAKE_SOURCE_DIR}/src/misc.c"
    "${CMAKE_SOURCE_DIR}/src/nicedb.c"
    "${CMAKE_SOURCE_DIR}/src/pkill.c"
    "${CMAKE_SOURCE_DIR}/src/quest.c"
    "${CMAKE_SOURCE_DIR}/src/save.c"
    "${CMAKE_SOURCE_DIR}/src/skills.c"
    "${CMAKE_SOURCE_DIR}/src/special.c"
    "${CMAKE_SOURCE_DIR}/src/string_safe.c"
    "${CMAKE_SOURCE_DIR}/src/update.c"
    "${CMAKE_SOURCE_DIR}/src/wizlist.c"
)

add_executable(${TARGET_NAME} ${SRC_FILES})

target_include_directories(${TARGET_NAME} PRIVATE "${CMAKE_SOURCE_DIR}/src")

target_compile_definitions(${TARGET_NAME} PRIVATE ROM)

option(ENABLE_SANITIZERS "Enable address and undefined sanitizers for debug validation" OFF)

if(ENABLE_SANITIZERS)
    target_compile_options(${TARGET_NAME} PRIVATE -fsanitize=address -fsanitize=undefined)
    target_link_options(${TARGET_NAME} PRIVATE -fsanitize=address -fsanitize=undefined)
endif()

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
)

# Link against math (m), compression (z), and crypto (crypt)
target_link_libraries(${TARGET_NAME} PRIVATE m z crypt)
