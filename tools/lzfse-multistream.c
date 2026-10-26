// Decode a file that contains many independent lzfse streams back to back,
// writing the concatenated output. Uses the lzfse decoder state to find where
// each stream ends (unlike lzfse_decode_buffer, which stops after the first).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "lzfse_internal.h"

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s IN OUT\n", argv[0]);
        return 2;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 2; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *src = malloc(sz);
    if (fread(src, 1, sz, f) != (size_t)sz) { perror("read"); return 2; }
    fclose(f);

    FILE *o = fopen(argv[2], "wb");
    if (!o) { perror(argv[2]); return 2; }

    size_t outcap = 256 << 20;
    uint8_t *out = malloc(outcap);
    lzfse_decoder_state *s = malloc(sizeof *s);

    s->src = src;
    s->src_end = src + sz;
    int nstreams = 0;
    uint64_t total = 0;
    while (s->src < s->src_end) {
        uint8_t *cur = s->src;
        memset(s, 0, sizeof *s);
        s->src = cur;
        s->src_begin = cur;
        s->src_end = src + sz;
        s->dst = out;
        s->dst_begin = out;
        s->dst_end = out + outcap;
        int status = lzfse_decode(s);
        if (status == LZFSE_STATUS_DST_FULL) {
            fprintf(stderr, "stream %d: output buffer full at in=%ld - growing\n",
                    nstreams, (long)(cur - src));
            outcap *= 2;
            out = realloc(out, outcap);
            if (!out) { fprintf(stderr, "OOM\n"); return 1; }
            s->src = cur;   // retry the same stream
            continue;
        }
        if (status != LZFSE_STATUS_OK) {
            fprintf(stderr, "stream %d: status %d at input offset %ld\n",
                    nstreams, status, (long)(cur - src));
            return 1;
        }
        fwrite(out, 1, s->dst - out, o);
        total += s->dst - out;
        nstreams++;
        if ((nstreams % 500) == 0)
            fprintf(stderr, "stream %d: in %ld / %ld, out %ld\n", nstreams,
                    (long)(s->src - src), sz, (long)total);
    }
    fprintf(stderr, "done: %d streams, %llu bytes out\n", nstreams,
            (unsigned long long)total);
    fclose(o);
    return 0;
}
