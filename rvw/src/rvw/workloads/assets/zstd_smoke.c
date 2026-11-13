/* Deterministic static-context compression and exact decompression check. */
#define ZSTD_STATIC_LINKING_ONLY
#include "zstd.h"
#include <string.h>
#include <errno.h>
void *_sbrk(ptrdiff_t increment) { (void)increment; errno=ENOMEM; return (void *)-1; }
static unsigned char input[262144], compressed[300000], restored[262144];
static unsigned long long cworkspace[524288], dworkspace[32768];
int main(void) {
    for (unsigned i=0; i<sizeof(input); i++) input[i]=(unsigned char)((i/127) ^ (i%31));
    ZSTD_CCtx *c = ZSTD_initStaticCCtx(cworkspace, sizeof(cworkspace));
    ZSTD_DCtx *d = ZSTD_initStaticDCtx(dworkspace, sizeof(dworkspace));
    if (!c || !d) return 1;
    size_t n = ZSTD_compressCCtx(c, compressed, sizeof(compressed), input, sizeof(input), 1);
    if (ZSTD_isError(n) || n >= sizeof(input)/2) return 2;
    size_t size = ZSTD_decompressDCtx(d, restored, sizeof(restored), compressed, n);
    return ZSTD_isError(size) || size != sizeof(input) || memcmp(input, restored, size);
}
