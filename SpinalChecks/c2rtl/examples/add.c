/* Inputs: unsigned 4-bit. Output: sum modulo 16. No signed overflow. */
uint32_t reference(uint32_t a, uint32_t b) { return (a + b) & 15u; }
