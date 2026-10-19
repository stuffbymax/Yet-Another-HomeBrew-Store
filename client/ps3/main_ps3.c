#include "../common/ui.h"
#ifndef YAHBS_STORE_URL
#define YAHBS_STORE_URL "https://store.example.com"
#endif
extern int plat_net_init(void);
int main(void) { plat_net_init(); ui_run(YAHBS_STORE_URL, "ps3"); return 0; }
