/* Shift count is b modulo 4, so every shift is defined in uint32_t. */
uint32_t reference(uint32_t a, uint32_t b) { return (a << (b & 3u)) & 15u; }
