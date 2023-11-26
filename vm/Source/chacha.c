/*
I wrote this by reference to https://datatracker.ietf.org/doc/rfc7539/

NB: For cryptographic purposes, everything is little-endian.
For generating pseudo-random numbers, it makes no difference.
*/


#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include "chacha.h"

static uint32_t rol(uint32_t value, int nr_bits) {
	return (value << nr_bits) | (value >> (32 - nr_bits));
}

static void quarter_round(uint32_t *a, uint32_t *b, uint32_t *c, uint32_t *d) {
	/*
	Section 2.1:
	The basic operation of the ChaCha algorithm is the quarter round.  It
	operates on four 32-bit unsigned integers, denoted a, b, c, and d.
	*/
	*a += *b; *d = rol(*d ^ *a, 16);
	*c += *d; *b = rol(*b ^ *c, 12);
	*a += *b; *d = rol(*d ^ *a, 8);
	*c += *d; *b = rol(*b ^ *c, 7);
}

void chacha_test_quarter_round() {
	// Test vector given in Section 2.2.1

	uint32_t a = 0x11111111;
	uint32_t b = 0x01020304;
	uint32_t c = 0x9b8d6f43;
	uint32_t d = 0x01234567;

	quarter_round(&a, &b, &c, &d);

	bool passed = (
		(a == 0xea2a92f4) &&
		(b == 0xcb1cf8ce) &&
		(c == 0x4581472e) &&
		(d == 0x5881c4bb)
	);

	fprintf(stderr, "ChaCha20 quarter_round test %s\n", passed ? "passed" : "failed");
}


static void full_round_pair(uint32_t *state) {
	// Column Rounds
	quarter_round(&state[0], &state[4], &state[8], &state[12]);
	quarter_round(&state[1], &state[5], &state[9], &state[13]);
	quarter_round(&state[2], &state[6], &state[10], &state[14]);
	quarter_round(&state[3], &state[7], &state[11], &state[15]);
	// Diagonal Rounds
	quarter_round(&state[0], &state[5], &state[10], &state[15]);
	quarter_round(&state[1], &state[6], &state[11], &state[12]);
	quarter_round(&state[2], &state[7], &state[8], &state[13]);
	quarter_round(&state[3], &state[4], &state[9], &state[14]);
}

void chacha_make_noise(ChaCha_Block *dst, const ChaCha_Seed *seed) {
	ChaCha_Block start, work;
	start.noise[0] = 0x61707865;
	start.noise[1] = 0x3320646e;
	start.noise[2] = 0x79622d32;
	start.noise[3] = 0x6b206574;
	memcpy(&start.noise[4], seed, sizeof(ChaCha_Seed));
	memcpy(&work, &start, sizeof(ChaCha_Block));
	for (int i = 0; i < 10; i++) full_round_pair(work.noise);
	for (int i = 0; i < 16; i++) dst->noise[i] = start.noise[i] + work.noise[i];
}

void chacha_test_make_noise() {
	// Test vector given in Section 2.3.2

	ChaCha_Seed seed = {
		.count = 1,
		.nonce = {0x09000000, 0x4a000000, 0x00000000},
	};
	for (int i = 0; i < 8; i++) seed.key[i] = 0x03020100 + (i*0x04040404);

	ChaCha_Block block;
	chacha_make_noise(&block, &seed);

	ChaCha_Block expected = { .noise = {
	   0xe4e7f110,  0x15593bd1,  0x1fdd0f50,  0xc47120a3,
	   0xc7f4d1c7,  0x0368c033,  0x9aaa2204,  0x4e6cd4c3,
	   0x466482d2,  0x09aa9f07,  0x05d7c214,  0xa2028bd9,
	   0xd19c12b5,  0xb94e16de,  0xe883d0cb,  0x4e3c50a2,
	} };

	bool passed = !memcmp(&block, &expected, sizeof(ChaCha_Block));
	fprintf(stderr, "ChaCha20 make_noise test %s\n", passed ? "passed" : "failed");
}
