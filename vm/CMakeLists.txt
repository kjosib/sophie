# CMakeList.txt : CMake project for SophieVM, include source and define
# project specific logic here.
#
cmake_minimum_required (VERSION 3.8)

# Enable Hot Reload for MSVC compilers if supported.
if (POLICY CMP0141)
  cmake_policy(SET CMP0141 NEW)
  set(CMAKE_MSVC_DEBUG_INFORMATION_FORMAT "$<IF:$<AND:$<C_COMPILER_ID:MSVC>,$<CXX_COMPILER_ID:MSVC>>,$<$<CONFIG:Debug,RelWithDebInfo>:EditAndContinue>,$<$<CONFIG:Debug,RelWithDebInfo>:ProgramDatabase>>")
endif()

project ("SophieVM")
include_directories(SYSTEM "/SDL2-2.30.3/include")
link_directories("/SDL2-2.30.3/lib/x64")

# Add source to this project's executable.
add_executable (SophieVM
	"Source/chunk.c"  "Source/debug.c"  "Source/main.c" "Source/memory.c" "Source/value.c" 
	"Source/vm.c" "Source/assembler.c" "Source/scanner.c" "Source/isa.c" "Source/parser.c"
	"Source/string.c" "Source/table.c" "Source/gc.c" "Source/function.c" "Source/record.c"
	"Source/native.c" "Source/actor.c" "Source/chacha.c" "Source/platform_specific.c"
	"Source/ffi.c"   "Source/game.c"  "Source/dispatch.c"

	"Source/common.h" "Source/opcodes.h" "Source/prep.h"
	"Source/chacha.h" "Source/platform_specific.h"
 "Source/debug.h")

set_target_properties(SophieVM PROPERTIES OUTPUT_NAME "svm")

target_link_libraries(SophieVM SDL2)

if (CMAKE_VERSION VERSION_GREATER 3.12)
  set_property(TARGET SophieVM PROPERTY CXX_STANDARD 20)
endif()

# Platform specific
if(WIN32)
	target_link_libraries(SophieVM bcrypt)
endif()


# TODO: Add tests and install targets if needed.
