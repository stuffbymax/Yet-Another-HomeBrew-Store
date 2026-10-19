/* YAHBS shared UI: software-rendered, identical on every console. Platforms provide a framebuffer
 * and a button source; everything else (layout, input, download flow) lives here. */
#ifndef YAHBS_UI_H
#define YAHBS_UI_H
#include <stdint.h>
#include "yahbs.h"

typedef struct { uint32_t *px; int w, h, stride; } ui_fb;   /* 0x00RRGGBB, stride in pixels */
enum { BTN_UP = 1, BTN_DOWN = 2, BTN_LEFT = 4, BTN_RIGHT = 8, BTN_OK = 16, BTN_BACK = 32, BTN_REFRESH = 64 };

typedef enum { UI_LIST, UI_DETAIL, UI_MESSAGE } ui_screen;
typedef enum { UI_PEND_NONE, UI_PEND_LOAD, UI_PEND_DOWNLOAD } ui_pending;

typedef struct ui_state {
  const char *base_url, *platform;
  yahbs_app apps[YAHBS_MAX_APPS];
  int n, sel, top;
  ui_screen screen;
  ui_pending pending;                /* queued, not started */
  ui_pending active;                 /* currently running (what the busy screen should show) */
  char msg[256]; int msg_ok;
  unsigned long long dl_done, dl_total;
  int busy;                          /* 1 while a blocking network call runs */
  int quit;
  void (*redraw)(struct ui_state *); /* platform: draw + present, used for progress updates */
} ui_state;

void ui_init(ui_state *u, const char *base_url, const char *platform);
void ui_step(ui_state *u, unsigned buttons);   /* may block on network when something is pending */
void ui_draw(const ui_state *u, ui_fb *fb);

/* PLATFORM (framebuffer + pad). Implemented per console. */
int plat_fb_get(ui_fb *fb);                    /* current back buffer; 0 on success */
void plat_present(void);                       /* flip/vsync */
unsigned plat_poll_buttons(void);              /* newly pressed buttons since last call (BTN_* mask) */
void plat_sleep_ms(int ms);

/* Standard main loop used by every console entry point. */
void ui_run(const char *base_url, const char *platform);
#endif
