#include "common.h"
#include "platform_specific.h"

#ifdef _WINDOWS

// This nest of includes is cribbed from Microsoft's public example (on GitHub)
// for how to invoke BCryptGenRandom, which is apparently the recommended
// source of genuine random bits on Windows these days.
#define WIN32_NO_STATUS
#include <windows.h>
#undef WIN32_NO_STATUS
#include <winternl.h>
#include <ntstatus.h>
#include <winerror.h>
#include <bcrypt.h>

void platform_entropy(void *dst, size_t size) {
	NTSTATUS status;
	status = BCryptGenRandom(NULL, dst, (ULONG)size, BCRYPT_USE_SYSTEM_PREFERRED_RNG);
	if (!NT_SUCCESS(status)) crashAndBurn("Windows failed to be random");
}

#else

void platform_entropy(void *dst, size_t size) {
	FILE *fh = fopen("/dev/urandom", "rb");
	if (fh == NULL) crashAndBurn("unable to open random seed source");
	size_t cb = fread(dst, sizeof(uint8_t), size, fh);
	if (cb < size) crashAndBurn("random seed source did not cooperate");
	fclose(fh);
}

#endif // _WINDOWS

