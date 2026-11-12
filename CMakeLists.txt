cmake_minimum_required(VERSION 3.20)

project(TOC2026 LANGUAGES C)

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

set(TARGET_NAME rom)

# Place build outputs in dedicated directories. TOC_BIN_DIR (and
# TOC_OBJ_DIR) default to the repository's bin/ and obj/, where the docs,
# the area scripts (../bin/rom) and CI look; a second build tree -- the
# sanitizer one beside the Release one -- can point elsewhere so the two
# never overwrite one binary (2026-11-12: a Release rebuild silently
# replaced the ASan bin/rom a test was about to use).
set(TOC_BIN_DIR "${CMAKE_SOURCE_DIR}/bin" CACHE PATH "Where the rom binary is written")
set(TOC_OBJ_DIR "${CMAKE_SOURCE_DIR}/obj" CACHE PATH "Where archives and libraries are written")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${TOC_BIN_DIR}")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${TOC_OBJ_DIR}")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${TOC_OBJ_DIR}")

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
    src/achievements.c
    src/act_comm.c
    src/act_info.c
    src/act_move.c
    src/act_obj.c
    src/act_wiz.c
    src/color.c
    src/combat_rules.c
    src/comm.c
    src/const.c
    src/container.c
    src/corpses.c
    src/db.c
    src/disaster.c
    src/dummy.c
    src/dstring.c
    src/text_fold.c
    src/edit.c
    src/fight.c
    src/gear_compare.c
    src/gmcp.c
    src/handler.c
    src/hunt.c
    src/hyrule.c
    src/interp.c
    src/list.c
    src/magic.c
    src/magic2.c
    src/misc.c
    src/numparse.c
    src/oracle.c
    src/pkill.c
    src/quest.c
    src/save.c
    src/skills.c
    src/season.c
    src/holiday.c
    src/holiday_rules.c
    src/speak_filter.c
    src/special.c
    src/string_safe.c
    src/telnet_proto.c
    src/stubs.c
    src/update.c
    src/walkto.c
    src/jail.c
    src/build.c
    src/changes.c
    src/diary.c
    src/abilities.c
    src/blackmarket.c
    src/fixes.c
    src/goblin.c
    src/maps.c
    src/rested.c
    src/recovery.c
    src/recycle.c
    src/memguard.c
    src/memrange.c
    src/memtrack.c
    src/heroes.c
    src/restores.c
    src/alignment.c
    src/playlog.c
    src/hyrulelog.c
    src/resurrect.c
    src/wizlist.c
    src/dnsasync.c
    src/connguard.c
    src/netaddr.c
    src/guardstore.c
    src/lockwindow.c
    src/tcpkeep.c
    src/loginlock.c
    src/password.c
)

add_executable(${TARGET_NAME})
target_sources(${TARGET_NAME} PRIVATE ${SRC_FILES})

# -rdynamic on Linux, as the Makefile: crash.log's backtrace (playlog.c)
# then names the game's functions rather than bare addresses.
set_target_properties(${TARGET_NAME} PROPERTIES ENABLE_EXPORTS ON)

target_include_directories(${TARGET_NAME} PRIVATE "${CMAKE_SOURCE_DIR}/src")

target_compile_definitions(${TARGET_NAME} PRIVATE ROM)

# Match the Makefile's -Dunix. CMAKE_C_EXTENSIONS is OFF, so this builds as
# strict -std=c17, where GCC does not predefine `unix`. merc.h defines it as
# a fallback, but only from the point merc.h is included, so any `unix` guard
# above that include behaves differently between the two build systems.
if(UNIX)
    target_compile_definitions(${TARGET_NAME} PRIVATE unix)
endif()

option(ENABLE_SANITIZERS "Enable address and undefined sanitizers for debug validation" OFF)

# Silent narrowing -- an int stored into a 16-bit field, the class behind
# the WIMPY and pool bugs -- a shadowed local and a signed/unsigned
# comparison. The whole tree is clean under these (strict-warnings sweep,
# 2026-11-12) and they are always on; TOC_STRICT_CONVERSION, which CI sets,
# makes any of them fail the build. tests/test_strict_warnings.py holds the
# same line for gcc. See AGENTS.md, "Strict Warnings".
option(TOC_STRICT_CONVERSION "Treat conversion, sign and shadow warnings as errors (CI)" OFF)
#
# The second pass (2026-11-12) made the tree clean under -Wcast-qual,
# -Wmissing-prototypes, -Wunused-parameter and gcc's -Warith-conversion
# (an int sum stored back into a sh_int; clang has no such flag, so it is
# passed to gcc alone). They are held to the same line.
set(TOC_CONVERSION_WARNINGS
    -Wshadow
    -Wsign-compare
    -Wconversion
    -Wsign-conversion
    -Wcast-qual
    -Wmissing-prototypes
    -Wunused-parameter
    -Wstrict-prototypes
    -Wold-style-definition
    $<$<C_COMPILER_ID:GNU>:-Warith-conversion>
    $<$<C_COMPILER_ID:GNU>:-Wformat-overflow=2>
)
set(TOC_CONVERSION_ERRORS
    -Werror=shadow
    -Werror=sign-compare
    -Werror=conversion
    -Werror=sign-conversion
    -Werror=cast-qual
    -Werror=missing-prototypes
    -Werror=unused-parameter
    -Werror=strict-prototypes
    -Werror=old-style-definition
    $<$<C_COMPILER_ID:GNU>:-Werror=arith-conversion>
    $<$<C_COMPILER_ID:GNU>:-Werror=format-overflow>
    $<$<C_COMPILER_ID:GNU>:-Werror=format-truncation>
)

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
        -Wno-strict-aliasing
        ${TOC_CONVERSION_WARNINGS}
        $<$<BOOL:${TOC_STRICT_CONVERSION}>:${TOC_CONVERSION_ERRORS}>
        $<$<AND:$<BOOL:${ENABLE_SANITIZERS}>,$<CONFIG:Debug>>:${SANITIZER_FLAGS}>
)

target_link_options(
    ${TARGET_NAME}
    PRIVATE
        $<$<AND:$<BOOL:${ENABLE_SANITIZERS}>,$<CONFIG:Debug>>:${SANITIZER_FLAGS}>
)

# Link against math (m) and crypto (crypt, Linux only — macOS provides it in libc)
target_link_libraries(${TARGET_NAME} PRIVATE m)
if(NOT APPLE)
    target_link_libraries(${TARGET_NAME} PRIVATE crypt)
endif()

# zlib backs MCCP2 output compression (src/telnet_proto.c).
find_package(ZLIB REQUIRED)
target_link_libraries(${TARGET_NAME} PRIVATE ZLIB::ZLIB)

# One worker thread makes hostname lookups off the game loop (src/dnsasync.c).
find_package(Threads REQUIRED)
target_link_libraries(${TARGET_NAME} PRIVATE Threads::Threads)
