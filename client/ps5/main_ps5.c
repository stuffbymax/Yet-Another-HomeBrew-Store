/* Headless YAHBS for PS5: reads app IDs (one per line) from /data/yahbs/queue.txt, downloads each one
 * through the signed-catalog + SHA-256 path, and writes results to /data/yahbs/log.txt. */
#include "../common/ui.h"
#include <stdio.h>
#include <stdlib.h>
#ifndef YAHBS_STORE_URL
#define YAHBS_STORE_URL "https://store.example.com"
#endif
static yahbs_app apps[YAHBS_MAX_APPS];
int main(void) {
  plat_mkdir(plat_download_dir());
  FILE *log = fopen("/data/yahbs/log.txt", "a"); if (!log) log = stderr;
  int n = yahbs_fetch_catalog(YAHBS_STORE_URL, "ps5", apps, YAHBS_MAX_APPS);
  if (n < 0) { fprintf(log, "catalog: %s\n", yahbs_strerror(n)); return 1; }
  fprintf(log, "catalog ok, %d apps\n", n);
  FILE *q = fopen("/data/yahbs/queue.txt", "r"); if (!q) { fprintf(log, "no queue.txt\n"); return 0; }
  char line[32];
  while (fgets(line, sizeof line, q)) {
    int id = atoi(line);
    for (int i = 0; i < n; i++) if (apps[i].id == id) {
      char path[300], note[200];
      snprintf(path, sizeof path, "%s/%d.%s", plat_download_dir(), id, apps[i].ext);
      int rc = yahbs_download(YAHBS_STORE_URL, &apps[i], path);
      if (rc == 0 && plat_install(path, &apps[i], note, sizeof note) == 0) fprintf(log, "%s\n", note);
      else fprintf(log, "app %d failed: %s\n", id, yahbs_strerror(rc));
    }
  }
  fclose(q); if (log != stderr) fclose(log);
  return 0;
}
