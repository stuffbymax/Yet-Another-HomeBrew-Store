/* YAHBS for PS4 (OpenOrbis).
 * Store URL: read from /data/yahbs/config.txt (one line, must start with https://), else the build-time default. */
#include "../common/ui.h"
#include <stdio.h>
#include <string.h>
#ifndef YAHBS_STORE_URL
#define YAHBS_STORE_URL "https://store.example.com"
#endif
extern int plat_net_init(void);

static char g_url[200];
static void load_url(void) {
  snprintf(g_url, sizeof g_url, "%s", YAHBS_STORE_URL);
  FILE *f = fopen("/data/yahbs/config.txt", "r");
  if (!f) return;
  char b[200];
  if (fgets(b, sizeof b, f)) {
    size_t n = strlen(b);
    while (n && (b[n - 1] == '\n' || b[n - 1] == '\r' || b[n - 1] == ' ' || b[n - 1] == '/')) b[--n] = 0;
    if (n > 8 && strncmp(b, "https://", 8) == 0) snprintf(g_url, sizeof g_url, "%s", b);
  }
  fclose(f);
}

int main(void) {
  plat_net_init();
  load_url();
  ui_run(g_url, "ps4");
  return 0;
}
