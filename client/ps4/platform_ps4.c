/* PS4 platform layer (OpenOrbis).  STATUS: compiles and links with OpenOrbis v0.5.4 (LLVM 18) and packages
 * into a .pkg; never run on a console. Video/pad calls follow the toolchain's own graphics/input samples.
 * Networking + TLS come from common/http_tls.c (mbedTLS over BSD sockets), so certificate checking is
 * identical on every console. */
#include "../common/ui.h"
#include <orbis/libkernel.h>
#include <orbis/VideoOut.h>      /* [CHECK] */
#include <orbis/Pad.h>           /* [CHECK] */
#include <orbis/UserService.h>   /* [CHECK] */
#include <orbis/Net.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>

#define W 1920
#define H 1080
#define NBUF 2

static int g_video = -1, g_pad = -1, g_front = 0;
static uint32_t *g_buf[NBUF];
static ui_fb g_fb[NBUF];

static int init_video(void) {
  if (g_video >= 0) return 0;
  g_video = sceVideoOutOpen(ORBIS_VIDEO_USER_MAIN, ORBIS_VIDEO_OUT_BUS_MAIN, 0, NULL);  /* [CHECK] */
  if (g_video < 0) return -1;
  size_t bytes = (size_t)W * H * 4, aligned = (bytes + 0x1fffff) & ~(size_t)0x1fffff;
  off_t phys; void *base = NULL;
  if (sceKernelAllocateDirectMemory(0, sceKernelGetDirectMemorySize(), aligned * NBUF, 0x200000, 3, &phys) < 0) return -1;
  if (sceKernelMapDirectMemory(&base, aligned * NBUF, 0x33, 0, phys, 0x200000) < 0) return -1;
  void *addrs[NBUF];
  for (int i = 0; i < NBUF; i++) {
    g_buf[i] = (uint32_t *)((char *)base + i * aligned); addrs[i] = g_buf[i];
    g_fb[i] = (ui_fb){ g_buf[i], W, H, W };
  }
  OrbisVideoOutBufferAttribute attr;
  sceVideoOutSetBufferAttribute(&attr, 0x80000000 /* B8G8R8A8 sRGB */,
                                1 /* linear tiling */, 0 /* 16:9 */, W, H, W);
  return sceVideoOutRegisterBuffers(g_video, 0, addrs, NBUF, &attr) < 0 ? -1 : 0;
}

int plat_fb_get(ui_fb *fb) {
  if (init_video() != 0) return -1;
  *fb = g_fb[g_front ^ 1]; return 0;                       /* draw into the buffer that is not on screen */
}
void plat_present(void) {
  sceVideoOutSubmitFlip(g_video, g_front ^ 1, ORBIS_VIDEO_OUT_FLIP_VSYNC, 0);
  g_front ^= 1;
  sceKernelUsleep(16000);   /* alpha: fixed ~60 Hz pacing; poll sceVideoOutGetFlipStatus() later to avoid tearing */
}

unsigned plat_poll_buttons(void) {
  static unsigned prev;
  if (g_pad < 0) {
    int uid; scePadInit();
    if (sceUserServiceInitialize(NULL) < 0 || sceUserServiceGetInitialUser(&uid) < 0) return 0;
    g_pad = scePadOpen(uid, 0, 0, NULL);
    if (g_pad < 0) return 0;
  }
  OrbisPadData d; if (scePadReadState(g_pad, &d) < 0) return 0;
  unsigned now = 0, b = d.buttons;
  if (b & ORBIS_PAD_BUTTON_UP) now |= BTN_UP;
  if (b & ORBIS_PAD_BUTTON_DOWN) now |= BTN_DOWN;
  if (b & ORBIS_PAD_BUTTON_LEFT) now |= BTN_LEFT;
  if (b & ORBIS_PAD_BUTTON_RIGHT) now |= BTN_RIGHT;
  if (b & ORBIS_PAD_BUTTON_CROSS) now |= BTN_OK;
  if (b & ORBIS_PAD_BUTTON_CIRCLE) now |= BTN_BACK;
  if (b & ORBIS_PAD_BUTTON_SQUARE) now |= BTN_REFRESH;
  unsigned pressed = now & ~prev; prev = now; return pressed;
}
void plat_sleep_ms(int ms) { sceKernelUsleep((unsigned)ms * 1000u); }

/* ---- non-graphics platform services ---- */
int plat_entropy(void *d, unsigned char *out, size_t len, size_t *olen) {
  (void)d; FILE *f = fopen("/dev/urandom", "rb");   /* fail closed: no weak fallback for TLS */
  if (!f) return -1;
  *olen = fread(out, 1, len, f); fclose(f); return *olen == len ? 0 : -1;
}
long plat_time(void) { time_t t = time(NULL); return t > 1700000000 ? (long)t : 0; }  /* 0 => unknown clock */
const char *plat_download_dir(void) { return "/data/yahbs"; }
int plat_mkdir(const char *p) { struct stat s; return mkdir(p, 0755) == 0 || stat(p, &s) == 0 ? 0 : -1; }
int plat_install(const char *path, const yahbs_app *a, char *msg, size_t n) {
  /* A .pkg is installed by the console's own installer; we only stage the verified file. */
  snprintf(msg, n, "Verified %s v%s. Saved to %s. Install it from the PS4 package installer.", a->name, a->version, path);
  return 0;
}

/* The TLS layer needs the system network stack initialised once. */
int plat_net_init(void) { return sceNetInit() < 0 ? -1 : 0; }
