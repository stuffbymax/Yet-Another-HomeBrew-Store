/* PS4 platform layer (OpenOrbis). ALPHA - NOT TESTED ON HARDWARE.
 * Header names / signatures follow the OpenOrbis samples; if the build fails, compare with
 * $OO_PS4_TOOLCHAIN/include/orbis/{Http,Net,Ssl}.h and the toolchain's network sample. */
#include "../common/yahbs.h"
#include <orbis/libkernel.h>
#include <orbis/Http.h>
#include <orbis/Net.h>
#include <orbis/Ssl.h>

#ifndef SCE_HTTP_VERSION_1_1
#define SCE_HTTP_VERSION_1_1 2
#endif
#ifndef SCE_HTTP_METHOD_GET
#define SCE_HTTP_METHOD_GET 0
#endif

static int g_netPool = -1, g_ssl = -1, g_http = -1;

int plat_init(void) {
  if (g_http >= 0) return 0;
  if (sceNetInit() < 0) return -1;
  g_netPool = sceNetPoolCreate("yahbs", 1 * 1024 * 1024, 0);
  g_ssl = sceSslInit(512 * 1024);
  g_http = sceHttpInit(g_netPool, g_ssl, 512 * 1024);
  return g_http >= 0 ? 0 : -1;
}

int plat_http_get(const char *url, yahbs_sink sink, void *user) {
  if (plat_init() != 0) return -1;
  int tmpl = sceHttpCreateTemplate(g_http, "YAHBS/0.1 (PS4)", SCE_HTTP_VERSION_1_1, 1);
  if (tmpl < 0) return -1;
  /* TODO(security, before beta): load CA certificates and make sure the TLS callback
   * REJECTS invalid certificates. Never ship a build that accepts any certificate. */
  int conn = sceHttpCreateConnectionWithURL(tmpl, url, 1);
  int req = conn < 0 ? conn : sceHttpCreateRequestWithURL(conn, SCE_HTTP_METHOD_GET, url, 0);
  int status = -1;
  if (req >= 0 && sceHttpSendRequest(req, NULL, 0) >= 0) {
    int code = 0;
    if (sceHttpGetStatusCode(req, &code) >= 0) status = code;
    static unsigned char buf[16 * 1024];
    int n;
    while (status == 200 && (n = sceHttpReadData(req, buf, sizeof buf)) > 0)
      if (sink(buf, (size_t)n, user)) { status = -1; break; }
    if (status == 200 && n < 0) status = -1;
  }
  if (req >= 0) sceHttpDeleteRequest(req);
  if (conn >= 0) sceHttpDeleteConnection(conn);
  sceHttpDeleteTemplate(tmpl);
  return status;
}
