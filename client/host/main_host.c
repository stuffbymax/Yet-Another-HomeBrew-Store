/* Test harness:  ./yahbs_host https://store.example ps4 [download-id]  */
#include "../common/yahbs.h"
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "usage: %s BASE_URL ps3|ps4|ps5 [ID]\n", argv[0]); return 2; }
  static yahbs_app apps[YAHBS_MAX_APPS];
  int n = yahbs_fetch_catalog(argv[1], argv[2], apps, YAHBS_MAX_APPS);
  if (n < 0) { fprintf(stderr, "catalog error %d (%s)\n", n, yahbs_strerror(n)); return 1; }
  for (int i = 0; i < n; i++)
    printf("%4d  %-30s v%-8s %10llu bytes\n", apps[i].id, apps[i].name, apps[i].version, apps[i].size);
  if (argc > 3) {
    int id = atoi(argv[3]);
    for (int i = 0; i < n; i++) if (apps[i].id == id) {
      int rc = yahbs_download(argv[1], &apps[i], "download.bin");  if (rc) fprintf(stderr, "%s\n", yahbs_strerror(rc));
      printf("download: %s (%d)\n", rc == 0 ? "OK, hash verified" : "FAILED", rc); return rc != 0;
    }
    fprintf(stderr, "id %d not in catalog\n", id); return 1;
  }
  return 0;
}
