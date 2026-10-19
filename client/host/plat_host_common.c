/* PC implementation of the non-network platform functions (for testing the core and the UI). */
#include "../common/yahbs.h"
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

int plat_entropy(void *d, unsigned char *out, size_t len, size_t *olen) {
  (void)d; FILE *f = fopen("/dev/urandom", "rb"); if (!f) return -1;
  *olen = fread(out, 1, len, f); fclose(f); return *olen == len ? 0 : -1;
}
long plat_time(void) { return (long)time(NULL); }
const char *plat_download_dir(void) { const char *e = getenv("YAHBS_DL_DIR"); return e ? e : "downloads"; }
int plat_mkdir(const char *p) { return mkdir(p, 0700) == 0 || access(p, 0) == 0 ? 0 : -1; }
int plat_install(const char *path, const yahbs_app *a, char *msg, size_t n) {
  (void)a; snprintf(msg, n, "Saved and verified: %s", path); return 0;
}
