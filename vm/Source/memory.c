#include "common.h"

/*
This module is specifically concerned with non-collectable immovable memory.
This includes the hash tables and most ancillary objects the compiler produces.
*/

void *reallocate(void *pointer, size_t newSize) {
	if (newSize == 0) {
		free(pointer);
		return NULL;
	}
	else {
		void *result = realloc(pointer, newSize);
		if (result == NULL) {
			crashAndBurn("Out of memory");
		}
		else {
			return result;
		}
	}
}
