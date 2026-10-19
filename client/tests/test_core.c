/* Unit tests for catalog verification. Fixtures are produced by gen_fixtures.py (same key as pubkey.h). */
#include "../common/yahbs.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *slurp(const char *p, size_t *n) {
  FILE *f = fopen(p, "rb"); if (!f) { perror(p); exit(2); }
  fseek(f, 0, SEEK_END); *n = (size_t)ftell(f); rewind(f);
  char *b = malloc(*n + 1); if (fread(b, 1, *n, f) != *n) exit(2); b[*n] = 0; fclose(f); return b;
}
static int fails;
#define CHECK(name, cond) do { int ok_ = (cond); printf("%-52s %s\n", name, ok_ ? "PASS" : "FAIL"); if (!ok_) fails++; } while (0)

int main(int argc, char **argv) {
  const char *d = argc > 1 ? argv[1] : "fixtures"; char p[300]; size_t n, body; yahbs_app apps[8];
  snprintf(p, sizeof p, "%s/good_ps4.tsv", d); char *good = slurp(p, &n);
  CHECK("valid signed catalog verifies", yahbs_verify_catalog(good, n, "ps4", &body) == 0);
  CHECK("  ...and parses 2 apps", yahbs_parse_catalog(good, body, apps, 8) == 2);
  CHECK("  ...fields are right", apps[0].id == 1 && !strcmp(apps[0].ext, "pkg") && apps[0].size == 1234);
  CHECK("same catalog rejected for another platform", yahbs_verify_catalog(good, n, "ps5", &body) != 0);

  char *t = strdup(good); char *q = strstr(t, "\t1234\t"); q[1] = '9';        /* change size 1234 -> 9234 */
  CHECK("modified row (size) is rejected", yahbs_verify_catalog(t, n, "ps4", &body) == YAHBS_ERR_SIG);
  free(t); t = strdup(good); q = strstr(t, "aaaaaaaa"); q[0] = 'b';           /* change a hash digit */
  CHECK("modified sha256 is rejected", yahbs_verify_catalog(t, n, "ps4", &body) == YAHBS_ERR_SIG);
  free(t); t = strdup(good); t[n - 3] = t[n - 3] == '0' ? '1' : '0';          /* corrupt the signature */
  CHECK("corrupted signature is rejected", yahbs_verify_catalog(t, n, "ps4", &body) == YAHBS_ERR_SIG);
  free(t);
  CHECK("truncated catalog is rejected", yahbs_verify_catalog(good, n - 20, "ps4", &body) == YAHBS_ERR_SIG);

  /* appended rows after the signature must not be accepted */
  char *ext = malloc(n + 200); memcpy(ext, good, n);
  strcpy(ext + n, "9\tEvil\t1\tps4\t10\taaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\tpkg\n");
  CHECK("rows appended after the signature rejected", yahbs_verify_catalog(ext, strlen(ext), "ps4", &body) == YAHBS_ERR_SIG);

  snprintf(p, sizeof p, "%s/old_ps4.tsv", d); size_t on; char *old = slurp(p, &on);
  CHECK("correctly signed but stale (replayed) catalog rejected", yahbs_verify_catalog(old, on, "ps4", &body) == YAHBS_ERR_STALE);
  snprintf(p, sizeof p, "%s/unsigned_ps4.tsv", d); size_t un; char *uns = slurp(p, &un);
  CHECK("unsigned catalog rejected", yahbs_verify_catalog(uns, un, "ps4", &body) == YAHBS_ERR_SIG);
  snprintf(p, sizeof p, "%s/otherkey_ps4.tsv", d); size_t kn; char *ok2 = slurp(p, &kn);
  CHECK("catalog signed by a different key rejected", yahbs_verify_catalog(ok2, kn, "ps4", &body) == YAHBS_ERR_SIG);

  /* parser hardening */
  const char *bad = "1\tA\t1\tps4\t10\tnothex\tpkg\n2\tB\t1\tps4\t10\t"
                    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\texe\n"
                    "3\tC\t1\tps4\t99999999999\taaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\tpkg\n";
  CHECK("parser skips bad hash / bad ext / oversized", yahbs_parse_catalog(bad, strlen(bad), apps, 8) == 0);
  printf("\n%s\n", fails ? "SOME TESTS FAILED" : "ALL PASSED");
  return fails != 0;
}
