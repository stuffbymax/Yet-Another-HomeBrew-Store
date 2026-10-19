/* PS5 platform layer (ps5-payload-sdk).  STATUS: UNVERIFIED and HEADLESS.
 *
 * A PS5 payload is an ELF that a homebrew-enabled console runs in the background. Whether and how it can
 * take over the display and read the pad depends on the host environment, which I could not verify, so
 * the on-screen UI is NOT wired up here. What is implemented (and shared with the other consoles):
 * signed-catalog fetch, TLS with pinned CA, hash-verified download. main_ps5.c drives it from a queue file.
 * The 4 display/pad functions below return "unavailable"; fill them in once you know your target's API,
 * and ui_run() will light up unchanged. */
#include "../common/ui.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

int plat_fb_get(ui_fb *fb) { (void)fb; return -1; }
void plat_present(void) {}
unsigned plat_poll_buttons(void) { return 0; }
void plat_sleep_ms(int ms) { usleep((unsigned)ms * 1000u); }

int plat_entropy(void *d, unsigned char *out, size_t len, size_t *olen) {
  (void)d; FILE *f = fopen("/dev/urandom", "rb");
  if (!f) return -1;                                   /* fail closed */
  *olen = fread(out, 1, len, f); fclose(f); return *olen == len ? 0 : -1;
}
long plat_time(void) { time_t t = time(NULL); return t > 1700000000 ? (long)t : 0; }
const char *plat_download_dir(void) { return "/data/yahbs"; }
int plat_mkdir(const char *p) { struct stat s; return mkdir(p, 0755) == 0 || stat(p, &s) == 0 ? 0 : -1; }
int plat_install(const char *path, const yahbs_app *a, char *msg, size_t n) {
  /* .elf payloads are only staged: running unreviewed code is the user's explicit, separate action. */
  snprintf(msg, n, "Verified %s v%s. Saved to %s.", a->name, a->version, path);
  return 0;
}
