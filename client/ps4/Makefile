# YAHBS PS4 client (OpenOrbis). Run:  source ~/yahbs-sdk/env-ps4.sh && make && make pkg
# ALPHA: modelled on the OpenOrbis sample Makefile. If upstream changed flags/tool names, diff against
# $(OO_PS4_TOOLCHAIN)/samples/*/Makefile.
ifndef OO_PS4_TOOLCHAIN
$(error OO_PS4_TOOLCHAIN not set - run: source ~/yahbs-sdk/env-ps4.sh)
endif
TARGET := yahbs
OUT := build
SRC := main_ps4.c platform_ps4.c ../common/yahbs.c ../common/sha256.c
OBJ := $(addprefix $(OUT)/,$(notdir $(SRC:.c=.o)))
CONTENT_ID := IV0000-YAHB00001_00-YAHBSALPHA0000001

CFLAGS := --target=x86_64-pc-freebsd12-elf -fPIC -funwind-tables -c -O2 -Wall \
          -isystem $(OO_PS4_TOOLCHAIN)/include
LDFLAGS := -m elf_x86_64 -pie --script $(OO_PS4_TOOLCHAIN)/link.x --eh-frame-hdr \
           -L$(OO_PS4_TOOLCHAIN)/lib
LIBS := -lc -lkernel -lSceNet -lSceSsl -lSceHttp

all: $(OUT)/eboot.bin
$(OUT):; mkdir -p $(OUT)
vpath %.c . ../common
$(OUT)/%.o: %.c | $(OUT)
	clang $(CFLAGS) -o $@ $<
$(OUT)/$(TARGET).elf: $(OBJ)
	ld.lld $(LDFLAGS) $(OO_PS4_TOOLCHAIN)/lib/crt1.o $(OBJ) $(LIBS) -o $@
$(OUT)/eboot.bin: $(OUT)/$(TARGET).elf
	create-fself -in=$< -out=$(OUT)/$(TARGET).oelf --eboot=$@ --paramsfo=sce_sys/param.sfo --authinfo=0x3800000000000011

# Package: see README "Packaging" - needs sce_sys/param.sfo (+ icon0.png) then create-gp4 / PkgTool.Core.
pkg: $(OUT)/eboot.bin
	cd $(OUT) && create-gp4 -out pkg.gp4 --content-id=$(CONTENT_ID) --files "eboot.bin sce_sys/param.sfo" && \
	PkgTool.Core pkg_build pkg.gp4 .
clean:; rm -rf $(OUT)
.PHONY: all pkg clean
