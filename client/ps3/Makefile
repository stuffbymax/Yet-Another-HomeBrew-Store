# YAHBS for PS3 (PSL1GHT).  UNVERIFIED skeleton based on the PSL1GHT sample Makefiles.
#   source ~/yahbs-sdk/env-ps3.sh
#   ../../toolchain/build_mbedtls.sh   (PS3 cross build, see README)   then:
#   make STORE_URL=https://store.example.com YAHBS_PS3_RANDOM_SYSCALL=<n> && make pkg
ifeq ($(strip $(PSL1GHT)),)
$(error PSL1GHT not set - source ~/yahbs-sdk/env-ps3.sh)
endif
include $(PSL1GHT)/ppu_rules
TARGET   := yahbs
TITLE    := YAHBS
APPID    := YAHBS0001
CONTENTID:= UP0001-$(APPID)_00-YAHBS00000000001
MBEDTLS  ?= $(HOME)/yahbs-sdk/mbedtls-ps3
STORE_URL?= https://store.example.com
COMMON   := yahbs.c sha256.c ui.c http_tls.c vendor/monocypher.c vendor/monocypher-ed25519.c
SRC      := main_ps3.c platform_ps3.c $(addprefix ../common/,$(COMMON))
CFLAGS   := -O2 -Wall -mcpu=cell -I../common -I../common/vendor -I$(MBEDTLS)/include \
            -DYAHBS_NO_GETADDRINFO -DYAHBS_STORE_URL=\"$(STORE_URL)\" \
            $(if $(YAHBS_PS3_RANDOM_SYSCALL),-DYAHBS_PS3_RANDOM_SYSCALL=$(YAHBS_PS3_RANDOM_SYSCALL)) $(MACHDEP) -I$(PORTLIBS)/include
LDFLAGS  := $(MACHDEP) -L$(MBEDTLS)/lib -L$(PORTLIBS)/lib
LIBS     := -lmbedtls -lmbedx509 -lmbedcrypto -lrsx -lgcm_sys -lio -lsysutil -lnet -lsysmodule -lrt -llv2 -lm
OBJS     := $(SRC:.c=.o)

all: $(TARGET).self
%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@
$(TARGET).elf: $(OBJS)
	$(CC) $(OBJS) $(LDFLAGS) $(LIBS) -o $@
pkg: $(TARGET).self
	$(PYTHON) $(PS3DEV)/bin/pkg.py --contentid $(CONTENTID) pkgdir $(TARGET).pkg   # [CHECK] see PSL1GHT sample "pkg" rule
clean:; rm -f $(OBJS) $(TARGET).elf $(TARGET).self $(TARGET).pkg
.PHONY: all pkg clean
