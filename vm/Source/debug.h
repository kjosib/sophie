#pragma once

#ifdef _DEBUG

//#define DEBUG_PRINT_GLOBALS
//#define DEBUG_PRINT_CODE
//#define DEBUG_TRACE_EXECUTION
//#define DEBUG_TRACE_QUEUE
//#define DEBUG_STRESS_GC
//#define DEBUG_ANNOUNCE_GC_MINOR
//#define DEBUG_ANNOUNCE_GC_MAJOR
#define USE_FINALIZERS 0  // This feature is probably broken right now, so disable it for the moment.

# else

#define USE_FINALIZERS 0  // In any case, the feature is certainly not ready for prime time.

#endif // _DEBUG

