#pragma once
/*
I wrote this by reference to https://datatracker.ietf.org/doc/rfc7539/

NB: For cryptographic purposes, everything is little-endian.
For generating pseudo-random numbers, it makes no difference.
*/


#include <stdint.h>

/*
	Section 2.3:
	The inputs to ChaCha20 are:
*/
typedef struct {
	uint32_t key[8];   // i.e. 256 bits = 32 bytes
	uint32_t count;    // enough for 256 gigabytes = 2^32 blocks.
	uint32_t nonce[3]; // i.e.  96 bits = 12 bytes
} ChaCha_Seed;

/*
	The outputs from ChaCha20 are:
*/
typedef union {
	// 64 bytes of effectively-random noise, no matter how you slice it:
	uint32_t noise[16];
	uint64_t noise_64[8];
	uint16_t noise_16[32];
	uint8_t  noise_8[64];
} ChaCha_Block;


void chacha_make_noise(ChaCha_Block *dst, const ChaCha_Seed *seed);

void chacha_test_quarter_round();
void chacha_test_make_noise();
