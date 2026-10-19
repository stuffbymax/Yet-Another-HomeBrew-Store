#include "yahbs.h"
#include "sha256.h"
#include "vendor/monocypher-ed25519.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if __has_include("pubkey.h")
#include "pubkey.h"
#else
#error "common/pubkey.h missing: copy pubkey.h.example and paste your server's public key (see README)"
#endif

#define CATALOG_MAX_BYTES (256 * 1024)
#define APP_MAX_BYTES (1024ULL * 1024 * 1024)
#define MAX_CATALOG_AGE_SEC (2L * 24 * 3600)   /* replay window; skipped when the console clock is unknown */
#define MAX_CLOCK_AHEAD_SEC (24L * 3600)

static const unsigned char PUBKEY[32] = YAHBS_PUBKEY;

const char *yahbs_strerror(int c) {
  switch (c) {
  case YAHBS_OK: return "ok";
  case YAHBS_ERR_NET: return "network error";
  case YAHBS_ERR_PARSE: return "bad catalog";
  case YAHBS_ERR_IO: return "storage error";
  case YAHBS_ERR_HASH: return "download failed verification";
  case YAHBS_ERR_TOO_BIG: return "response too large";
  case YAHBS_ERR_URL: return "bad or insecure URL";
  case YAHBS_ERR_SIG: return "catalog signature invalid";
  case YAHBS_ERR_CANCEL: return "cancelled";
  case YAHBS_ERR_STALE: return "catalog is out of date";
  default: return "error";
  }
}

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
static int is_hex(const char *s, size_t n) {
  if (strlen(s) != n) return 0;
  for (; *s; s++) if (!((*s >= '0' && *s <= '9') || (*s >= 'a' && *s <= 'f'))) return 0;
  return 1;
}
static int hexval(char c) { return c <= '9' ? c - '0' : c - 'a' + 10; }

int yahbs_verify_catalog(const char *t, size_t n, const char *platform, size_t *body_len) {
  /* find the last line that starts with "#sig\t" */
  size_t sig_at = (size_t)-1;
  for (size_t i = n; i-- > 0;)
    if ((i == 0 || t[i - 1] == '\n') && n - i >= 5 && memcmp(t + i, "#sig\t", 5) == 0) { sig_at = i; break; }
  if (sig_at == (size_t)-1) return YAHBS_ERR_SIG;
  const char *hex = t + sig_at + 5; size_t hl = n - sig_at - 5;
  if (hl > 0 && hex[hl - 1] == '\n') hl--;
  if (hl != 128) return YAHBS_ERR_SIG;
  unsigned char sig[64]; char hs[129]; memcpy(hs, hex, 128); hs[128] = 0;
  if (!is_hex(hs, 128)) return YAHBS_ERR_SIG;
  for (int i = 0; i < 64; i++) sig[i] = (unsigned char)(hexval(hs[2 * i]) << 4 | hexval(hs[2 * i + 1]));
  if (crypto_ed25519_check(sig, PUBKEY, (const unsigned char *)t, sig_at) != 0) return YAHBS_ERR_SIG;

  /* signed header: "#ts\t<unix>\n#plat\t<platform>\n" - stops replaying another platform's catalog */
  if (sig_at < 4 || memcmp(t, "#ts\t", 4) != 0) return YAHBS_ERR_SIG;
  char *end; long ts = strtol(t + 4, &end, 10);
  if (*end != '\n') return YAHBS_ERR_SIG;
  char want[32]; int wl = snprintf(want, sizeof want, "#plat\t%s\n", platform);
  if (strncmp(end + 1, want, (size_t)wl) != 0) return YAHBS_ERR_SIG;
  long now = plat_time();
  if (now > 0 && (now - ts > MAX_CATALOG_AGE_SEC || ts - now > MAX_CLOCK_AHEAD_SEC)) return YAHBS_ERR_STALE;
  *body_len = sig_at;
  return YAHBS_OK;
}

int yahbs_parse_catalog(const char *text, size_t len, yahbs_app *out, int max) {
  int count = 0; const char *p = text, *end = text + len;
  while (p < end && count < max) {
    const char *nl = memchr(p, '\n', (size_t)(end - p)); if (!nl) nl = end;
    const char *f[7]; size_t fl[7]; int nf = 0; const char *s = p;
    if (*p != '#') {
      for (const char *q = p; q <= nl && nf < 7; q++)
        if (q == nl || *q == '\t') { f[nf] = s; fl[nf] = (size_t)(q - s); nf++; s = q + 1; }
    }
    if (nf == 7) {              /* '#' header lines and malformed rows are skipped */
      yahbs_app a; memset(&a, 0, sizeof a); char num[24];
      int ok = copy_field(a.name, sizeof a.name, f[1], fl[1]) &&
               copy_field(a.version, sizeof a.version, f[2], fl[2]) &&
               copy_field(a.platform, sizeof a.platform, f[3], fl[3]) &&
               copy_field(a.sha256, sizeof a.sha256, f[5], fl[5]) &&
               copy_field(a.ext, sizeof a.ext, f[6], fl[6]) &&
               copy_field(num, sizeof num, f[0], fl[0]);
      if (ok) { a.id = atoi(num); ok = a.id > 0; }
      if (ok) { ok = copy_field(num, sizeof num, f[4], fl[4]); if (ok) a.size = strtoull(num, NULL, 10); }
      if (ok) ok = !strcmp(a.ext, "pkg") || !strcmp(a.ext, "zip") || !strcmp(a.ext, "elf");
      if (ok && is_hex(a.sha256, 64) && a.size > 0 && a.size <= APP_MAX_BYTES) out[count++] = a;
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
  int rc; size_t body = 0;
  if (g.overflow) rc = YAHBS_ERR_TOO_BIG;
  else if (st != 200) rc = YAHBS_ERR_NET;
  else if ((rc = yahbs_verify_catalog(g.p ? g.p : "", g.n, platform, &body)) == YAHBS_OK)
    rc = yahbs_parse_catalog(g.p, body, out, max);
  free(g.p);
  return rc;
}

/* ---- download ---- */
typedef struct { FILE *f; sha256_ctx h; unsigned long long n, limit, last; int io_err, cancel;
                 yahbs_progress cb; void *user; } dl;
static int dl_sink(const void *d, size_t len, void *u) {
  dl *x = u;
  if (x->n + len > x->limit) return 1;          /* more bytes than the signed catalog promised */
  if (fwrite(d, 1, len, x->f) != len) { x->io_err = 1; return 1; }
  sha256_update(&x->h, d, len); x->n += len;
  if (x->cb && (x->n - x->last >= 65536 || x->n == x->limit)) {
    x->last = x->n;
    if (x->cb(x->n, x->limit, x->user)) { x->cancel = 1; return 1; }
  }
  return 0;
}

int yahbs_download_ex(const char *base, const yahbs_app *app, const char *dest,
                      yahbs_progress cb, void *user) {
  char url[512], tmp[512], hex[65]; dl x; int rc;
  if (!url_ok(base) || strlen(base) > 200 || strlen(dest) > 480) return YAHBS_ERR_URL;
  snprintf(url, sizeof url, "%s/app/%d/download", base, app->id);
  snprintf(tmp, sizeof tmp, "%s.part", dest);
  memset(&x, 0, sizeof x); x.limit = app->size; x.cb = cb; x.user = user; sha256_init(&x.h);
  x.f = fopen(tmp, "wb"); if (!x.f) return YAHBS_ERR_IO;
  int st = plat_http_get(url, dl_sink, &x);
  if (fclose(x.f) != 0) x.io_err = 1;
  if (x.cancel) rc = YAHBS_ERR_CANCEL;
  else if (x.io_err) rc = YAHBS_ERR_IO;
  else if (st != 200) rc = YAHBS_ERR_NET;
  else if (x.n != app->size) rc = YAHBS_ERR_HASH;
  else { sha256_hex(&x.h, hex); rc = strcmp(hex, app->sha256) == 0 ? YAHBS_OK : YAHBS_ERR_HASH; }
  if (rc == YAHBS_OK && rename(tmp, dest) != 0) rc = YAHBS_ERR_IO;
  if (rc != YAHBS_OK) remove(tmp);
  return rc;
}
int yahbs_download(const char *base, const yahbs_app *app, const char *dest) {
  return yahbs_download_ex(base, app, dest, NULL, NULL);
}
