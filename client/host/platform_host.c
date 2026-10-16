/* Linux/macOS implementation of the platform layer using libcurl: lets you test the core on a PC. */
#include "../common/yahbs.h"
#include <curl/curl.h>

typedef struct { yahbs_sink sink; void *user; } ctx;
static size_t cb(char *p, size_t s, size_t n, void *u) {
  ctx *c = u; return c->sink(p, s * n, c->user) ? 0 : s * n;
}
int plat_http_get(const char *url, yahbs_sink sink, void *user) {
  CURL *h = curl_easy_init(); if (!h) return -1;
  ctx c = { sink, user }; long status = 0;
  curl_easy_setopt(h, CURLOPT_URL, url);
  curl_easy_setopt(h, CURLOPT_WRITEFUNCTION, cb);
  curl_easy_setopt(h, CURLOPT_WRITEDATA, &c);
  curl_easy_setopt(h, CURLOPT_FOLLOWLOCATION, 0L);
  curl_easy_setopt(h, CURLOPT_PROTOCOLS_STR, "https"
#ifdef YAHBS_ALLOW_HTTP
                   ",http"
#endif
  );
  curl_easy_setopt(h, CURLOPT_TIMEOUT, 600L);
  curl_easy_setopt(h, CURLOPT_USERAGENT, "YAHBS-client/0.1-host");
  CURLcode rc = curl_easy_perform(h);
  curl_easy_getinfo(h, CURLINFO_RESPONSE_CODE, &status);
  curl_easy_cleanup(h);
  return rc == CURLE_OK ? (int)status : -1;
}
