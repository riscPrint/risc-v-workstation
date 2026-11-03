/* Inputs: unsigned 4-bit. Output: low four product bits. */
uint32_t reference(uint32_t a, uint32_t b) { return (a * b) & 15u; }
