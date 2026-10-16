/* YAHBS client core: platform-independent. Each console supplies plat_http_get(). */
#ifndef YAHBS_H
#define YAHBS_H
#include <stddef.h>

#define YAHBS_MAX_APPS 256
typedef struct {
  int id;
  char name[65], version[21], platform[4], sha256[65];
  unsigned long long size;
} yahbs_app;

/* Receives body chunks. Return 0 to continue, non-zero to abort. */
typedef int (*yahbs_sink)(const void *data, size_t len, void *user);

/* PLATFORM LAYER (implemented per console): GET url, stream body to sink.
 * Returns HTTP status (e.g. 200) or a negative error code. */
int plat_http_get(const char *url, yahbs_sink sink, void *user);

/* CORE */
enum { YAHBS_OK = 0, YAHBS_ERR_NET = -1, YAHBS_ERR_PARSE = -2, YAHBS_ERR_IO = -3,
       YAHBS_ERR_HASH = -4, YAHBS_ERR_TOO_BIG = -5, YAHBS_ERR_URL = -6 };

/* Fetch catalog for "ps3"|"ps4"|"ps5". Returns number of apps (>=0) or a negative error. */
int yahbs_fetch_catalog(const char *base_url, const char *platform, yahbs_app *out, int max);
/* Download to dest_path; the file only appears there if size and SHA-256 match the catalog. */
int yahbs_download(const char *base_url, const yahbs_app *app, const char *dest_path);
/* Parses TSV text (modifies nothing). Exposed for tests. */
int yahbs_parse_catalog(const char *text, size_t len, yahbs_app *out, int max);
#endif
