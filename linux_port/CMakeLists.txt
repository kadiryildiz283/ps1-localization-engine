cmake_minimum_required(VERSION 3.16)
project(hp2_linux C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

find_package(SDL2 REQUIRED)
find_package(OpenGL REQUIRED)

add_executable(hp2_linux
    src/main.c
    src/dpsx.c
    src/tpsx.c
    src/lpsx.c
    src/audio_spu.c
    src/render_gl.c
    src/physics.c
)

target_include_directories(hp2_linux PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${SDL2_INCLUDE_DIRS}
)

target_link_libraries(hp2_linux PRIVATE ${SDL2_LIBRARIES} ${OPENGL_LIBRARIES} m)
target_compile_options(hp2_linux PRIVATE -Wall -Wextra -O2)
set_target_properties(hp2_linux PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
