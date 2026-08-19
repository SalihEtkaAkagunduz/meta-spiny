cmake_minimum_required(VERSION 3.0)
project(fbcp C)

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -O3 -Wall")

add_executable(fbcp fbcp.c)

# No dependencies - pure Linux framebuffer
target_link_libraries(fbcp)

install(TARGETS fbcp DESTINATION bin)
