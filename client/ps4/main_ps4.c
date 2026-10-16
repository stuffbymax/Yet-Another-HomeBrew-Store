/* YAHBS PS4 client, alpha 0.1: network + catalog + verified download.
 * Output goes to the kernel debug log (visible via UART / klog). The on-screen UI is the next milestone
 * (see README roadmap). */
#include "../common/yahbs.h"
#include <orbis/libkernel.h>
#include <stdio.h>

#define STORE_URL "https://store.example.com"   /* <- set to your server */
#define DOWNLOAD_DIR "/data/yahbs"

extern int plat_init(void);
static yahbs_app apps[YAHBS_MAX_APPS];

#define LOG(...) do { char _b[256]; snprintf(_b, sizeof _b, __VA_ARGS__); sceKernelDebugOutText(0, _b); } while (0)

int main(void) {
  LOG("YAHBS alpha starting\n");
  if (plat_init() != 0) { LOG("network init failed\n"); return 1; }
  int n = yahbs_fetch_catalog(STORE_URL, "ps4", apps, YAHBS_MAX_APPS);
  if (n < 0) { LOG("catalog error %d\n", n); return 1; }
  for (int i = 0; i < n; i++)
    LOG("[%d] %s v%s (%llu bytes)\n", apps[i].id, apps[i].name, apps[i].version, apps[i].size);
  /* Smoke test: fetch the first app to verify the whole pipeline. */
  if (n > 0) {
    char path[128]; snprintf(path, sizeof path, DOWNLOAD_DIR "/%d.bin", apps[0].id);
    LOG("download -> %d\n", yahbs_download(STORE_URL, &apps[0], path));
  }
  return 0;
}
