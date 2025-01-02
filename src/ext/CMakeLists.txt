cmake_minimum_required(VERSION 3.10)
project(blender_extension)

# 设置模块的源文件路径
set(EXT_SRC
    ${CMAKE_CURRENT_SOURCE_DIR}/amagatex.cpp
)

# 添加动态库 (MODULE 表示为动态加载的模块)
add_library(blender_extension MODULE ${EXT_SRC})

# 包含 Blender 的 Python API 头文件
include_directories(${CMAKE_SOURCE_DIR}/blender/source/blender/python)

# 链接 Blender 的库（确保路径正确）
target_link_libraries(blender_extension PRIVATE blender)

# 指定生成的目标路径
set_target_properties(blender_extension PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/Release
)
