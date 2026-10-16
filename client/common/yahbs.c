#include "yahbs.h"
#include "sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CATALOG_MAX_BYTES (256 * 1024)
#define APP_MAX_BYTES (1024ULL * 1024 * 1024)

static int url_ok(const char *base) {
  if (strncmp(base, "https://", 8) == 0) return 1;
#ifdef YAHBS_ALLOW_HTTP   /* development builds only */
  if (strncmp(base, "http://", 7) == 0) return 1;
#endif
  return 0;
}

/* ---- catalog ---- */
typedef struct { char *p; size_t n, cap; int overflow; } growbuf;
static int grow_sink(const void *d, size_t len, void *u) {
  growbuf *g = u;
  if (g->n + len > CATALOG_MAX_BYTES) { g->overflow = 1; return 1; }
  if (g->n + len + 1 > g->cap) {
    size_t nc = g->cap ? g->cap * 2 : 4096; while (nc < g->n + len + 1) nc *= 2;
    char *np = realloc(g->p, nc); if (!np) return 1; g->p = np; g->cap = nc;
  }
  memcpy(g->p + g->n, d, len); g->n += len; g->p[g->n] = 0; return 0;
}

static int copy_field(char *dst, size_t cap, const char *s, size_t len) {
  if (len == 0 || len >= cap) return 0;
  memcpy(dst, s, len); dst[len] = 0; return 1;
}
static int is_hex64(const char *s) {
  if (strlen(s) != 64) return 0;
  for (; *s; s++) if (!((*s >= '0' && *s <= '9') || (*s >= 'a' && *s <= 'f'))) return 0;
  return 1;
}

int yahbs_parse_catalog(const char *text, size_t len, yahbs_app *out, int max) {
  int count = 0; const char *p = text, *end = text + len;
  while (p < end && count < max) {
    const char *nl = memchr(p, '\n', (size_t)(end - p)); if (!nl) nl = end;
    const char *f[6]; size_t fl[6]; int nf = 0; const char *s = p;
    for (const char *q = p; q <= nl && nf < 6; q++)
      if (q == nl || *q == '\t') { f[nf] = s; fl[nf] = (size_t)(q - s); nf++; s = q + 1; }
    if (nf == 6) {              /* lines that don't have exactly 6 fields are skipped */
      yahbs_app a; memset(&a, 0, sizeof a); char num[24];
      int ok = copy_field(a.name, sizeof a.name, f[1], fl[1]) &&
               copy_field(a.version, sizeof a.version, f[2], fl[2]) &&
               copy_field(a.platform, sizeof a.platform, f[3], fl[3]) &&
               copy_field(a.sha256, sizeof a.sha256, f[5], fl[5]) &&
               copy_field(num, sizeof num, f[0], fl[0]);
      if (ok) { a.id = atoi(num); ok = a.id > 0; }
      if (ok) { ok = copy_field(num, sizeof num, f[4], fl[4]); if (ok) a.size = strtoull(num, NULL, 10); }
      if (ok && is_hex64(a.sha256) && a.size > 0 && a.size <= APP_MAX_BYTES) out[count++] = a;
    }
    p = nl + 1;
  }
  return count;
}

int yahbs_fetch_catalog(const char *base, const char *platform, yahbs_app *out, int max) {
  char url[512]; growbuf g = {0};
  if (!url_ok(base) || strlen(base) > 200) return YAHBS_ERR_URL;
  if (strcmp(platform, "ps3") && strcmp(platform, "ps4") && strcmp(platform, "ps5")) return YAHBS_ERR_URL;
  snprintf(url, sizeof url, "%s/api/v1/catalog.tsv?platform=%s", base, platform);
  int st = plat_http_get(url, grow_sink, &g);
  int rc;
  if (g.overflow) rc = YAHBS_ERR_TOO_BIG;
  else if (st != 200) rc = YAHBS_ERR_NET;
  else rc = yahbs_parse_catalog(g.p ? g.p : "", g.n, out, max);
  free(g.p);
  return rc;
}

/* ---- download ---- */
typedef struct { FILE *f; sha256_ctx h; unsigned long long n, limit; int io_err; } dl;
static int dl_sink(const void *d, size_t len, void *u) {
  dl *x = u;
  if (x->n + len > x->limit) return 1;          /* more bytes than the catalog promised */
  if (fwrite(d, 1, len, x->f) != len) { x->io_err = 1; return 1; }
  sha256_update(&x->h, d, len); x->n += len; return 0;
}

int yahbs_download(const char *base, const yahbs_app *app, const char *dest) {
  char url[512], tmp[512], hex[65]; dl x; int rc;
  if (!url_ok(base) || strlen(base) > 200 || strlen(dest) > 480) return YAHBS_ERR_URL;
  snprintf(url, sizeof url, "%s/app/%d/download", base, app->id);
  snprintf(tmp, sizeof tmp, "%s.part", dest);
  memset(&x, 0, sizeof x); x.limit = app->size; sha256_init(&x.h);
  x.f = fopen(tmp, "wb"); if (!x.f) return YAHBS_ERR_IO;
  int st = plat_http_get(url, dl_sink, &x);
  if (fclose(x.f) != 0) x.io_err = 1;
  if (x.io_err) rc = YAHBS_ERR_IO;
  else if (st != 200) rc = YAHBS_ERR_NET;
  else if (x.n != app->size) rc = YAHBS_ERR_HASH;
  else { sha256_hex(&x.h, hex); rc = strcmp(hex, app->sha256) == 0 ? YAHBS_OK : YAHBS_ERR_HASH; }
  if (rc == YAHBS_OK && rename(tmp, dest) != 0) rc = YAHBS_ERR_IO;
  if (rc != YAHBS_OK) remove(tmp);
  return rc;
}
