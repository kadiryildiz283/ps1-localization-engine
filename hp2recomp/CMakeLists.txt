cmake_minimum_required(VERSION 3.20)
# Bu proje, repo kökündeki mevcut psxrecomp/ checkout'ını kullanır
# (framework'ün önerdiği submodule düzeninin yerel karşılığı).
set(PSXRECOMP_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../psxrecomp" CACHE PATH
    "Path to psxrecomp")
# Gerçek yola çöz: Ninja, aynı çıktı dosyasını hem symlink/.. yazımıyla hem
# çözümlenmiş yolla tanımlayınca "defined as an output multiple times" verir.
get_filename_component(PSXRECOMP_ROOT "${PSXRECOMP_ROOT}" REALPATH)
if(NOT EXISTS "${PSXRECOMP_ROOT}/runtime/runtime.cmake")
    message(FATAL_ERROR
        "PSXRecomp runtime is missing: ${PSXRECOMP_ROOT}/runtime/runtime.cmake\n"
        "Set -DPSXRECOMP_ROOT=<path-to-psxrecomp>.")
endif()

project(HP2Recomp LANGUAGES C CXX)

# recomp-ui yok; netplay ve setup wizard kapalı (tek oyunculu port).
set(PSX_RECOMP_UI OFF CACHE BOOL
    "No recomp-ui submodule in this scaffold" FORCE)
# if(EXISTS "${PSXRECOMP_ROOT}/lib/recomp-net/CMakeLists.txt")
#     set(PSX_NETPLAY ON CACHE BOOL "Link recomp-net delay-sync" FORCE)
# endif()
# set(PSX_SETUP_WIZARD ON CACHE BOOL "First-run setup wizard" FORCE)
# HP2 PAL VSync(0) spins 1<<15 iterations and relies on Beetle R3000A load-wait
# cycles; native-cpu-spans under-charges loads and triggers VSync timeout/Port 1 starvation.
set(PSX_NATIVE_CPU_SPANS OFF CACHE BOOL
    "HP2 PAL VSync(0) requires faithful load-wait cycles" FORCE)
include("${PSXRECOMP_ROOT}/runtime/runtime.cmake")

set(PSX_PRELOADED_MODS "${CMAKE_CURRENT_SOURCE_DIR}/mods/preloaded")
if(NOT IS_DIRECTORY "${PSX_PRELOADED_MODS}")
    set(PSX_PRELOADED_MODS "NONE")
endif()

psxrecomp_add_game_runtime(psx-runtime
    PRELOADED_MODS_DIR "${PSX_PRELOADED_MODS}"
    # GAME_OVERLAY_STATIC_C, GEN_FULL_GLOB (çok-değerli) ÖNCE gelmeli:
    # wrapper bu anahtarı parse etmez, sonra gelirse GEN_FULL_GLOB yutar.
    # EURO1.GAM + diğer overlay'lerin statik native shard'ları (KUSEG dahil).
    GAME_OVERLAY_STATIC_C "${CMAKE_CURRENT_SOURCE_DIR}/aot_static/overlays_static.c"
    # ENABLE_NETPLAY_IF_PRESENT
    # ENABLE_SETUP_WIZARD
    WINDOW_TITLE "Harry Potter and the Chamber of Secrets Recompiled"
    DEFAULT_GAME_CONFIG_PATH "game.toml"
    MAX_PLAYERS 1
    GEN_MARKER "generated/SLES_039.72_dispatch.c"
    GEN_FULL_GLOB "generated/SLES_039.72_full_*.c"
)

# Türkçe bayrak menüsü güvenilir plugin'i (mod system, runtime-only).
target_sources(psx-runtime PRIVATE src/tr_flag_menu.c)

foreach(_PSX_RUNTIME_CONFIG game.toml game_options.toml)
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/${_PSX_RUNTIME_CONFIG}")
        add_custom_command(TARGET psx-runtime POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${CMAKE_CURRENT_SOURCE_DIR}/${_PSX_RUNTIME_CONFIG}"
                "$<TARGET_FILE_DIR:psx-runtime>/${_PSX_RUNTIME_CONFIG}"
            COMMENT "Staging ${_PSX_RUNTIME_CONFIG}"
            VERBATIM)
    endif()
endforeach()
