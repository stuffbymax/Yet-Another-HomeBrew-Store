#include "ui.h"
#include "font8x16.h"
#include <stdio.h>
#include <string.h>

#define C_BG 0x0d1220
#define C_SURFACE 0x151c2f
#define C_SEL 0x23304f
#define C_LINE 0x26304a
#define C_TEXT 0xe7ebf4
#define C_MUTED 0x8e99b3
#define C_OK 0x33b58a
#define C_ERR 0xf0707a

static uint32_t plat_color(const char *p) {
  return !strcmp(p, "ps3") ? 0xe0629f : !strcmp(p, "ps4") ? 0x33b58a : 0x5b8cf0;
}

/* ---------- drawing ---------- */
static void rect(ui_fb *fb, int x, int y, int w, int h, uint32_t c) {
  if (x < 0) { w += x; x = 0; }
  if (y < 0) { h += y; y = 0; }
  if (x + w > fb->w) w = fb->w - x;
  if (y + h > fb->h) h = fb->h - y;
  for (int j = 0; j < h; j++) {
    uint32_t *row = fb->px + (size_t)(y + j) * fb->stride + x;
    for (int i = 0; i < w; i++) row[i] = c;
  }
}
static int text(ui_fb *fb, int x, int y, int s, const char *str, uint32_t c, int maxcols) {
  int col = 0;
  for (; *str && col < maxcols; str++, col++) {
    unsigned char ch = (unsigned char)*str; if (ch < 32 || ch > 126) ch = '?';
    const unsigned char *g = font8x16[ch - 32];
    for (int gy = 0; gy < 16; gy++) for (int gx = 0; gx < 8; gx++)
      if (g[gy] & (0x80 >> gx)) rect(fb, x + (col * 8 + gx) * s, y + gy * s, s, s, c);
  }
  return col;
}
static void fmt_size(unsigned long long n, char *o, size_t cap) {
  if (n < 1024) snprintf(o, cap, "%llu B", n);
  else if (n < 1024ULL * 1024) snprintf(o, cap, "%.1f KB", n / 1024.0);
  else if (n < 1024ULL * 1024 * 1024) snprintf(o, cap, "%.1f MB", n / 1048576.0);
  else snprintf(o, cap, "%.2f GB", n / 1073741824.0);
}

static void header(const ui_state *u, ui_fb *fb, int s, const char *sub) {
  int ch = 16 * s, pad = 2 * ch;
  rect(fb, 0, 0, fb->w, 3 * ch, C_SURFACE);
  rect(fb, 0, 3 * ch - s * 2, fb->w, s * 2, plat_color(u->platform));
  text(fb, pad, ch, s, "YAHBS", C_TEXT, 10);
  char t[48]; snprintf(t, sizeof t, "homebrew for %s", u->platform);
  for (char *p = t + 13; *p; p++) if (*p >= 'a' && *p <= 'z') *p -= 32;
  text(fb, pad + 7 * 8 * s, ch, s, t, C_MUTED, 40);
  if (sub) text(fb, fb->w - pad - (int)strlen(sub) * 8 * s, ch, s, sub, C_MUTED, 40);
}
static void footer(ui_fb *fb, int s, const char *hint) {
  int ch = 16 * s;
  rect(fb, 0, fb->h - 3 * ch, fb->w, 3 * ch, C_SURFACE);
  text(fb, 2 * ch, fb->h - 2 * ch, s, hint, C_MUTED, (fb->w - 4 * ch) / (8 * s));
}

void ui_draw(const ui_state *u, ui_fb *fb) {
  int s = fb->h / 360; if (s < 1) s = 1;
  int ch = 16 * s, pad = 2 * ch, cols = (fb->w - 2 * pad) / (8 * s);
  rect(fb, 0, 0, fb->w, fb->h, C_BG);

  if (u->busy && (u->active == UI_PEND_DOWNLOAD || u->pending == UI_PEND_DOWNLOAD)) {
    header(u, fb, s, NULL);
    const yahbs_app *a = &u->apps[u->sel];
    text(fb, pad, 5 * ch, s, "Downloading", C_MUTED, cols);
    text(fb, pad, 6 * ch + ch / 2, s, a->name, C_TEXT, cols);
    int bx = pad, by = 9 * ch, bw = fb->w - 2 * pad, bh = 2 * ch;
    rect(fb, bx, by, bw, bh, C_SURFACE);
    int fill = u->dl_total ? (int)((double)bw * (double)u->dl_done / (double)u->dl_total) : 0;
    rect(fb, bx, by, fill, bh, plat_color(u->platform));
    char t[64], a1[24], a2[24]; fmt_size(u->dl_done, a1, sizeof a1); fmt_size(u->dl_total, a2, sizeof a2);
    snprintf(t, sizeof t, "%s / %s", a1, a2);
    text(fb, pad, by + bh + ch, s, t, C_MUTED, cols);
    text(fb, pad, by + bh + 3 * ch, s, "Checking SHA-256 when finished", C_MUTED, cols);
    return;
  }
  if (u->busy) {
    header(u, fb, s, NULL);
    text(fb, pad, 6 * ch, s, "Loading catalog...", C_TEXT, cols);
    return;
  }

  if (u->screen == UI_LIST) {
    char sub[32]; snprintf(sub, sizeof sub, "%d apps", u->n);
    header(u, fb, s, sub);
    if (u->n == 0) text(fb, pad, 6 * ch, s, "No apps yet for this console.", C_MUTED, cols);
    int rowh = 3 * ch, top = 4 * ch, vis = (fb->h - top - 3 * ch) / rowh;
    for (int i = 0; i < vis && u->top + i < u->n; i++) {
      const yahbs_app *a = &u->apps[u->top + i]; int y = top + i * rowh;
      if (u->top + i == u->sel) {
        rect(fb, pad / 2, y, fb->w - pad, rowh - s * 2, C_SEL);
        rect(fb, pad / 2, y, 4 * s, rowh - s * 2, plat_color(u->platform));
      }
      char sz[24], t[96]; fmt_size(a->size, sz, sizeof sz);
      snprintf(t, sizeof t, "v%s   %s   %s", a->version, a->ext, sz);
      text(fb, pad, y + ch / 2, s, a->name, C_TEXT, cols);
      text(fb, pad, y + ch / 2 + ch, s, t, C_MUTED, cols);
    }
    footer(fb, s, "[OK] details    [REFRESH] reload    [BACK] exit");
  } else if (u->screen == UI_DETAIL) {
    const yahbs_app *a = &u->apps[u->sel];
    header(u, fb, s, NULL);
    char sz[24], t[128]; fmt_size(a->size, sz, sizeof sz);
    text(fb, pad, 5 * ch, s, a->name, C_TEXT, cols);
    snprintf(t, sizeof t, "version %s   %s   %s", a->version, a->ext, sz);
    text(fb, pad, 6 * ch + ch / 2, s, t, C_MUTED, cols);
    text(fb, pad, 9 * ch, s, "SHA-256", C_MUTED, cols);
    char h1[33], h2[33]; memcpy(h1, a->sha256, 32); h1[32] = 0; memcpy(h2, a->sha256 + 32, 32); h2[32] = 0;
    text(fb, pad, 10 * ch, s, h1, C_TEXT, cols);
    text(fb, pad, 11 * ch, s, h2, C_TEXT, cols);
    text(fb, pad, 13 * ch, s, "The file is checked against this hash before it is kept.", C_MUTED, cols);
    footer(fb, s, "[OK] download    [BACK] list");
  } else {
    header(u, fb, s, NULL);
    text(fb, pad, 5 * ch, s, u->msg_ok ? "Done" : "Something went wrong", u->msg_ok ? C_OK : C_ERR, cols);
    /* wrap message */
    int line = 0, len = (int)strlen(u->msg), pos = 0;
    while (pos < len && line < 8) {
      int take = len - pos < cols ? len - pos : cols; char row[160];
      memcpy(row, u->msg + pos, take); row[take] = 0;
      text(fb, pad, (7 + line) * ch + ch / 2, s, row, C_TEXT, cols); pos += take; line++;
    }
    footer(fb, s, "[OK] continue");
  }
}

/* ---------- logic ---------- */
void ui_init(ui_state *u, const char *base_url, const char *platform) {
  memset(u, 0, sizeof *u);
  u->base_url = base_url; u->platform = platform; u->screen = UI_LIST; u->pending = UI_PEND_LOAD;
}

static void message(ui_state *u, int ok, const char *fmt, const char *a) {
  snprintf(u->msg, sizeof u->msg, fmt, a); u->msg_ok = ok; u->screen = UI_MESSAGE;
}
static int on_progress(unsigned long long done, unsigned long long total, void *user) {
  ui_state *u = user; u->dl_done = done; u->dl_total = total;
  if (u->redraw) u->redraw(u);
  return 0;
}
static void safe_name(const char *in, char *out, size_t cap) {
  size_t j = 0;
  for (; *in && j + 1 < cap && j < 40; in++)
    out[j++] = ((*in >= 'a' && *in <= 'z') || (*in >= 'A' && *in <= 'Z') || (*in >= '0' && *in <= '9') ||
                *in == '-' || *in == '_') ? *in : '_';
  out[j] = 0;
}

static void do_pending(ui_state *u) {
  ui_pending p = u->pending; u->pending = UI_PEND_NONE; u->active = p;
  if (p == UI_PEND_LOAD) {
    int n = yahbs_fetch_catalog(u->base_url, u->platform, u->apps, YAHBS_MAX_APPS);
    u->busy = 0; u->active = UI_PEND_NONE;
    if (n < 0) { u->n = 0; message(u, 0, "Could not load the store: %s.", yahbs_strerror(n)); return; }
    u->n = n; u->sel = u->top = 0; u->screen = UI_LIST;
  } else if (p == UI_PEND_DOWNLOAD) {
    const yahbs_app *a = &u->apps[u->sel]; char nm[48], path[400], note[200];
    safe_name(a->name, nm, sizeof nm);
    plat_mkdir(plat_download_dir());
    snprintf(path, sizeof path, "%s/%d-%s.%s", plat_download_dir(), a->id, nm, a->ext);
    u->dl_done = 0; u->dl_total = a->size;
    int rc = yahbs_download_ex(u->base_url, a, path, on_progress, u);
    u->busy = 0; u->active = UI_PEND_NONE;
    if (rc != YAHBS_OK) { message(u, 0, "Download failed: %s. Nothing was saved.", yahbs_strerror(rc)); return; }
    if (plat_install(path, a, note, sizeof note) == 0) message(u, 1, "%s", note);
    else message(u, 0, "Verified but not installed: %s", note);
  }
}

void ui_step(ui_state *u, unsigned b) {
  if (u->pending) { u->busy = 1; do_pending(u); return; }
  if (u->screen == UI_LIST) {
    if (b & BTN_DOWN && u->sel + 1 < u->n) u->sel++;
    if (b & BTN_UP && u->sel > 0) u->sel--;
    if (b & BTN_RIGHT) u->sel = (u->sel + 6 < u->n) ? u->sel + 6 : (u->n ? u->n - 1 : 0);
    if (b & BTN_LEFT) u->sel = u->sel >= 6 ? u->sel - 6 : 0;
    if (u->sel < u->top) u->top = u->sel;
    if (u->sel >= u->top + 6) u->top = u->sel - 5;     /* roughly one screen of rows at 720p */
    if (b & BTN_OK && u->n) u->screen = UI_DETAIL;
    if (b & BTN_REFRESH) u->pending = UI_PEND_LOAD;
    if (b & BTN_BACK) u->quit = 1;
  } else if (u->screen == UI_DETAIL) {
    if (b & BTN_OK) {                                  /* next frame shows the progress screen */
      u->pending = UI_PEND_DOWNLOAD; u->busy = 1; u->dl_done = 0; u->dl_total = u->apps[u->sel].size;
    }
    if (b & BTN_BACK) u->screen = UI_LIST;
  } else if (b & (BTN_OK | BTN_BACK)) u->screen = UI_LIST;
  if (u->pending == UI_PEND_LOAD) u->busy = 1;
}

/* ---------- standard main loop ---------- */
static ui_state *g_u;
static void redraw_cb(ui_state *u) {
  ui_fb fb;
  if (plat_fb_get(&fb) == 0) { ui_draw(u, &fb); plat_present(); }
}
void ui_run(const char *base_url, const char *platform) {
  static ui_state u; g_u = &u;
  ui_init(&u, base_url, platform); u.redraw = redraw_cb; u.busy = 1;
  while (!u.quit) {
    redraw_cb(&u);
    unsigned b = u.pending ? 0 : plat_poll_buttons();
    ui_step(&u, b);
    if (!u.pending && !b) plat_sleep_ms(16);
  }
}
