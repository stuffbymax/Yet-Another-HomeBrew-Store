/* PS3 platform layer (PSL1GHT).  STATUS: UNVERIFIED - written from memory of the PSL1GHT samples; never
 * compiled against the real SDK or run on hardware. [CHECK] marks calls to compare with the samples in
 * $PSL1GHT/samples (rsxtest, pad). The PPU is BIG-ENDIAN; the shared core was tested under qemu-ppc64. */
#include "../common/ui.h"
#include <malloc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <net/net.h>
#include <sysutil/video.h>
#include <rsx/rsx.h>
#include <io/pad.h>
#include <sys/systime.h>
#include <lv2/syscalls.h>

#define CB_SIZE   0x100000
#define HOST_SIZE (32 * 1024 * 1024)
#define NBUF 2

static gcmContextData *ctx;
static int g_w, g_h, g_cur;
static uint32_t *g_buf[NBUF]; static uint32_t g_off[NBUF];
static int g_ready;
static uint32_t g_flip_id;

static void wait_flip(void) {
  while (gcmGetFlipStatus() != 0) usleep(200);
  gcmResetFlipStatus();
}

static int init_video(void) {
  if (g_ready) return 0;
  void *host = memalign(1024 * 1024, HOST_SIZE);
  if (!host) return -1;
  rsxInit(&ctx, CB_SIZE, HOST_SIZE, host);                                   /* [CHECK] */
  videoState st; videoResolution res;
  if (videoGetState(0, 0, &st) != 0 || videoGetResolution(st.displayMode.resolution, &res) != 0) return -1;
  g_w = res.width; g_h = res.height;
  videoConfiguration vc; memset(&vc, 0, sizeof vc);
  vc.resolution = st.displayMode.resolution; vc.format = VIDEO_BUFFER_FORMAT_XRGB; vc.pitch = g_w * 4;
  if (videoConfigure(0, &vc, NULL, 0) != 0) return -1;
  gcmSetFlipMode(GCM_FLIP_VSYNC);
  for (int i = 0; i < NBUF; i++) {
    g_buf[i] = (uint32_t *)rsxMemalign(64, (size_t)g_w * g_h * 4);
    if (!g_buf[i]) return -1;
    rsxAddressToOffset(g_buf[i], &g_off[i]);
    gcmSetDisplayBuffer(i, g_off[i], g_w * 4, g_w, g_h);
  }
  gcmResetFlipStatus(); g_ready = 1; return 0;
}

int plat_fb_get(ui_fb *fb) {
  if (init_video() != 0) return -1;
  *fb = (ui_fb){ g_buf[g_cur], g_w, g_h, g_w };   /* XRGB, native big-endian word == 0x00RRGGBB */
  return 0;
}
void plat_present(void) {
  gcmSetFlip(ctx, g_cur); rsxFlushBuffer(ctx); gcmSetWaitFlip(ctx);
  g_cur ^= 1; (void)g_flip_id;
  wait_flip();
}

unsigned plat_poll_buttons(void) {
  static unsigned prev; static int init;
  if (!init) { ioPadInit(7); init = 1; }
  padInfo pi; padData pd; ioPadGetInfo(&pi);
  unsigned now = 0;
  for (int i = 0; i < MAX_PADS; i++) if (pi.status[i]) {
    ioPadGetData(i, &pd);
    if (pd.BTN_UP) now |= BTN_UP;       if (pd.BTN_DOWN) now |= BTN_DOWN;
    if (pd.BTN_LEFT) now |= BTN_LEFT;   if (pd.BTN_RIGHT) now |= BTN_RIGHT;
    if (pd.BTN_CROSS) now |= BTN_OK;    if (pd.BTN_CIRCLE) now |= BTN_BACK;
    if (pd.BTN_SQUARE) now |= BTN_REFRESH;
  }
  unsigned pressed = now & ~prev; prev = now; return pressed;
}
void plat_sleep_ms(int ms) { usleep((unsigned)ms * 1000u); }

/* Entropy: TLS must NOT run on a weak source. The PS3 hardware RNG is an LV2 syscall; confirm its number
 * for your PSL1GHT/firmware and pass -DYAHBS_PS3_RANDOM_SYSCALL=<n>. Until then TLS refuses to start. */
int plat_entropy(void *d, unsigned char *out, size_t len, size_t *olen) {
  (void)d;
#ifdef YAHBS_PS3_RANDOM_SYSCALL
  u64 got = 0;
  if (Lv2Syscall2(YAHBS_PS3_RANDOM_SYSCALL, (u64)(uintptr_t)out, len) != 0) return -1;   /* [CHECK] */
  (void)got; *olen = len; return 0;
#else
  (void)out; (void)len; *olen = 0; return -1;
#endif
}
long plat_time(void) { time_t t = time(NULL); return t > 1700000000 ? (long)t : 0; }
const char *plat_download_dir(void) { return "/dev_hdd0/game/YAHBS0001/USRDIR/downloads"; }
int plat_mkdir(const char *p) {
  struct stat s; char tmp[256]; snprintf(tmp, sizeof tmp, "%s", p);
  for (char *q = tmp + 1; *q; q++) if (*q == '/') { *q = 0; mkdir(tmp, 0777); *q = '/'; }
  return mkdir(tmp, 0777) == 0 || stat(tmp, &s) == 0 ? 0 : -1;
}
int plat_install(const char *path, const yahbs_app *a, char *msg, size_t n) {
  snprintf(msg, n, "Verified %s v%s. Saved to %s. Install .pkg files from Game > Install Package Files.", a->name, a->version, path);
  return 0;
}
int plat_net_init(void) { return netInitialize() == 0 ? 0 : -1; }   /* [CHECK] */
