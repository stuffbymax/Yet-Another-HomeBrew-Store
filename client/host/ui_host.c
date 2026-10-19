/* Renders the real UI to PPM files, driven by a script of button presses.
 *   ./ui_host BASE_URL ps4 "DDOOB" outdir      (U D L R O B F = up down left right ok back refresh)
 * Frame 00 is the loading screen, then one frame after each key. */
#include "../common/ui.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static uint32_t px[1280 * 720]; static ui_fb fb = { px, 1280, 720, 1280 };
int plat_fb_get(ui_fb *f) { *f = fb; return 0; }
void plat_present(void) {}
unsigned plat_poll_buttons(void) { return 0; }
void plat_sleep_ms(int ms) { (void)ms; }

static void snap(const ui_state *u, const char *dir, int n) {
  char path[300]; snprintf(path, sizeof path, "%s/frame_%02d.ppm", dir, n);
  ui_draw(u, &fb);
  FILE *f = fopen(path, "wb"); if (!f) return;
  fprintf(f, "P6\n%d %d\n255\n", fb.w, fb.h);
  for (int i = 0; i < fb.w * fb.h; i++) { unsigned char c[3] = { px[i] >> 16, px[i] >> 8, px[i] }; fwrite(c, 1, 3, f); }
  fclose(f);
}
static const char *g_dir; static int g_progress_done;
static void on_redraw(ui_state *u) {            /* called during downloads: capture one mid-way frame */
  if (!g_progress_done && u->dl_total && u->dl_done * 2 >= u->dl_total) { g_progress_done = 1; snap(u, g_dir, 90); }
}
int main(int argc, char **argv) {
  if (argc < 5) { fprintf(stderr, "usage: %s URL ps3|ps4|ps5 SCRIPT OUTDIR\n", argv[0]); return 2; }
  static ui_state u; ui_init(&u, argv[1], argv[2]); u.busy = 1; u.redraw = on_redraw; g_dir = argv[4];
  int n = 0; snap(&u, argv[4], n++);
  ui_step(&u, 0);                         /* performs the catalog load */
  for (const char *k = argv[3]; *k; k++) {
    unsigned b = *k=='U'?BTN_UP:*k=='D'?BTN_DOWN:*k=='L'?BTN_LEFT:*k=='R'?BTN_RIGHT:*k=='O'?BTN_OK:*k=='B'?BTN_BACK:*k=='F'?BTN_REFRESH:0;
    ui_step(&u, b);
    if (u.pending) { snap(&u, argv[4], n++); ui_step(&u, 0); }   /* show busy/progress frame, then do the work */
    snap(&u, argv[4], n++);
  }
  return 0;
}
