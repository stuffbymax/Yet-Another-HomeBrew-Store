/* YAHBS client core: platform-independent. Each console supplies the plat_* functions below. */
#ifndef YAHBS_H
#define YAHBS_H
#include <stddef.h>

#define YAHBS_MAX_APPS 256
typedef struct {
  int id;
  char name[65], version[21], platform[4], sha256[65], ext[5];
  unsigned long long size;
} yahbs_app;

/* Receives body chunks. Return 0 to continue, non-zero to abort. */
typedef int (*yahbs_sink)(const void *data, size_t len, void *user);
/* Progress callback. Return non-zero to cancel the download. */
typedef int (*yahbs_progress)(unsigned long long done, unsigned long long total, void *user);

/* ---------------- PLATFORM LAYER (implemented once per console) ---------------- */
/* GET url, stream body to sink ONLY when status is 200. Returns HTTP status or negative on error.
 * Implementations MUST verify the server certificate (see http_tls.c) and MUST NOT follow redirects. */
int plat_http_get(const char *url, yahbs_sink sink, void *user);
long plat_time(void);                         /* unix seconds, or 0 if the clock is unknown */
const char *plat_download_dir(void);          /* where packages are stored */
int plat_mkdir(const char *path);             /* 0 on success or if it already exists */
/* After a verified download: install / stage it. Fills msg for the user. 0 = ok. */
int plat_install(const char *path, const yahbs_app *app, char *msg, size_t msglen);

/* ---------------- CORE ---------------- */
enum { YAHBS_OK = 0, YAHBS_ERR_NET = -1, YAHBS_ERR_PARSE = -2, YAHBS_ERR_IO = -3,
       YAHBS_ERR_HASH = -4, YAHBS_ERR_TOO_BIG = -5, YAHBS_ERR_URL = -6, YAHBS_ERR_SIG = -7,
       YAHBS_ERR_CANCEL = -8, YAHBS_ERR_STALE = -9 };

const char *yahbs_strerror(int code);

/* Fetch + VERIFY (Ed25519) the catalog for "ps3"|"ps4"|"ps5". Returns app count (>=0) or negative error. */
int yahbs_fetch_catalog(const char *base_url, const char *platform, yahbs_app *out, int max);
/* Download to dest_path; the file only appears there if size and SHA-256 match the signed catalog. */
int yahbs_download(const char *base_url, const yahbs_app *app, const char *dest_path);
int yahbs_download_ex(const char *base_url, const yahbs_app *app, const char *dest_path,
                      yahbs_progress cb, void *user);
/* Exposed for tests. verify returns 0 and sets *body_len if the signature, platform and age check out. */
int yahbs_verify_catalog(const char *text, size_t len, const char *platform, size_t *body_len);
int yahbs_parse_catalog(const char *text, size_t len, yahbs_app *out, int max);
#endif
