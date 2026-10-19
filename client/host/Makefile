# PC test build.  NET=tls (default, same code as PS3/PS5, needs libmbedtls-dev) or NET=curl.
NET ?= tls
CFLAGS ?= -O2 -Wall -Wextra -DYAHBS_ALLOW_HTTP -I../common -I../common/vendor   # drop ALLOW_HTTP for release
CORE = ../common/yahbs.c ../common/sha256.c ../common/vendor/monocypher.c ../common/vendor/monocypher-ed25519.c plat_host_common.c
ifeq ($(NET),tls)
NETSRC = ../common/http_tls.c
LIBS = -lmbedtls -lmbedx509 -lmbedcrypto
else
NETSRC = platform_host.c
LIBS = -lcurl
endif
all: yahbs_host ui_host
HDRS = $(wildcard ../common/*.h)
yahbs_host: main_host.c $(CORE) $(NETSRC) $(HDRS)
	$(CC) $(CFLAGS) -o $@ $^ $(LIBS)
ui_host: ui_host.c ../common/ui.c $(CORE) $(NETSRC) $(HDRS)
	$(CC) $(CFLAGS) -o $@ $^ $(LIBS)
clean:
	rm -f yahbs_host ui_host
