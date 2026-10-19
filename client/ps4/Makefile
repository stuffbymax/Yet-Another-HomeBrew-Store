# YAHBS for PS4 (OpenOrbis, LLVM release).  Based on the official hello_world sample Makefile.
#   source ~/yahbs-sdk/env-ps4.sh
#   (once) CC=clang AR=llvm-ar ../../toolchain/build_mbedtls.sh $HOME/yahbs-sdk/mbedtls-ps4 \
#          --target=x86_64-pc-freebsd12-elf -fPIC -funwind-tables -ffunction-sections \
#          -isysroot $OO_PS4_TOOLCHAIN -isystem $OO_PS4_TOOLCHAIN/include -DMBEDTLS_NO_PLATFORM_ENTROPY
#   make STORE_URL=https://store.example.com        -> IV0000-YAHB00001_00-YAHBSALPHA000001.pkg
ifndef OO_PS4_TOOLCHAIN
$(error OO_PS4_TOOLCHAIN not set - run: source ~/yahbs-sdk/env-ps4.sh)
endif
TITLE      := YAHBS
VERSION    := 0.10
TITLE_ID   := YAHB00001
CONTENT_ID := IV0000-YAHB00001_00-YAHBSALPHA000001
STORE_URL  ?= https://store.example.com
MBEDTLS    ?= $(HOME)/yahbs-sdk/mbedtls-ps4

TC   := $(OO_PS4_TOOLCHAIN)
TOOLS:= $(TC)/bin/linux
OUT  := build
COMMON := yahbs.c sha256.c ui.c http_tls.c vendor/monocypher.c vendor/monocypher-ed25519.c
SRC  := main_ps4.c platform_ps4.c $(addprefix ../common/,$(COMMON))
OBJS := $(addprefix $(OUT)/,$(notdir $(SRC:.c=.o)))
SAMPLE := $(TC)/samples/hello_world

CFLAGS := --target=x86_64-pc-freebsd12-elf -fPIC -funwind-tables -c -O2 -Wall \
          -isysroot $(TC) -isystem $(TC)/include \
          -I../common -I../common/vendor -I$(MBEDTLS)/include -DYAHBS_STORE_URL=\"$(STORE_URL)\"
LDFLAGS := -m elf_x86_64 -pie --script $(TC)/link.x --eh-frame-hdr -L$(TC)/lib -L$(MBEDTLS)/lib \
           -lmbedtls -lmbedx509 -lmbedcrypto -lc -lkernel -lSceNet -lSceVideoOut -lScePad -lSceUserService \
           $(TC)/lib/crt1.o

all: $(CONTENT_ID).pkg
vpath %.c . ../common ../common/vendor

$(OUT)/%.o: %.c | $(OUT)
	clang $(CFLAGS) -o $@ $<
$(OUT):; mkdir -p $(OUT)

$(OUT)/yahbs.elf: $(OBJS)
	ld.lld $(OBJS) -o $@ $(LDFLAGS)
eboot.bin: $(OUT)/yahbs.elf
	$(TOOLS)/create-fself -in=$< -out=$(OUT)/yahbs.oelf --eboot "eboot.bin" --paid 0x3800000000000011

# Support files every OpenOrbis package needs are taken from the toolchain's own sample (icon is a placeholder:
# put your own 512x512 PNG at pkg_files/sce_sys/icon0.png to override).
stage:
	mkdir -p sce_sys/about sce_module
	cp -n $(SAMPLE)/sce_sys/about/right.sprx sce_sys/about/
	cp -n $(SAMPLE)/sce_sys/icon0.png sce_sys/
	cp -n $(SAMPLE)/sce_module/libc.prx $(SAMPLE)/sce_module/libSceFios2.prx sce_module/

sce_sys/param.sfo: Makefile | stage
	$(TOOLS)/PkgTool.Core sfo_new $@
	$(TOOLS)/PkgTool.Core sfo_setentry $@ APP_TYPE --type Integer --maxsize 4 --value 1
	$(TOOLS)/PkgTool.Core sfo_setentry $@ APP_VER --type Utf8 --maxsize 8 --value '$(VERSION)'
	$(TOOLS)/PkgTool.Core sfo_setentry $@ ATTRIBUTE --type Integer --maxsize 4 --value 0
	$(TOOLS)/PkgTool.Core sfo_setentry $@ CATEGORY --type Utf8 --maxsize 4 --value 'gd'
	$(TOOLS)/PkgTool.Core sfo_setentry $@ CONTENT_ID --type Utf8 --maxsize 48 --value '$(CONTENT_ID)'
	$(TOOLS)/PkgTool.Core sfo_setentry $@ DOWNLOAD_DATA_SIZE --type Integer --maxsize 4 --value 0
	$(TOOLS)/PkgTool.Core sfo_setentry $@ SYSTEM_VER --type Integer --maxsize 4 --value 0
	$(TOOLS)/PkgTool.Core sfo_setentry $@ TITLE --type Utf8 --maxsize 128 --value '$(TITLE)'
	$(TOOLS)/PkgTool.Core sfo_setentry $@ TITLE_ID --type Utf8 --maxsize 12 --value '$(TITLE_ID)'
	$(TOOLS)/PkgTool.Core sfo_setentry $@ VERSION --type Utf8 --maxsize 8 --value '$(VERSION)'

pkg.gp4: eboot.bin sce_sys/param.sfo | stage
	$(TOOLS)/create-gp4 -out $@ --content-id=$(CONTENT_ID) \
	  --files "eboot.bin sce_sys/about/right.sprx sce_sys/param.sfo sce_sys/icon0.png sce_module/libc.prx sce_module/libSceFios2.prx"
$(CONTENT_ID).pkg: pkg.gp4
	$(TOOLS)/PkgTool.Core pkg_build $< .

clean:
	rm -rf $(OUT) eboot.bin pkg.gp4 sce_sys sce_module $(CONTENT_ID).pkg
.PHONY: all stage clean
