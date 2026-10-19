# YAHBS headless client for PS5 (ps5-payload-sdk).  UNVERIFIED skeleton.
#   source ~/yahbs-sdk/env-ps5.sh && make STORE_URL=https://store.example.com
# Needs mbedTLS built for the SDK (toolchain/build_mbedtls.sh).
ifeq ($(strip $(PS5_PAYLOAD_SDK)),)
$(error PS5_PAYLOAD_SDK not set - source ~/yahbs-sdk/env-ps5.sh)
endif
MBEDTLS  ?= $(HOME)/yahbs-sdk/mbedtls-ps5
STORE_URL?= https://store.example.com
COMMON   := yahbs.c sha256.c ui.c http_tls.c vendor/monocypher.c vendor/monocypher-ed25519.c
SRC      := main_ps5.c platform_ps5.c $(addprefix ../common/,$(COMMON))
CFLAGS   := -O2 -Wall -I../common -I../common/vendor -I$(MBEDTLS)/include -DYAHBS_STORE_URL=\"$(STORE_URL)\"
LDLIBS   := -L$(MBEDTLS)/lib -lmbedtls -lmbedx509 -lmbedcrypto
include $(PS5_PAYLOAD_SDK)/toolchain/prospero.mk     # [CHECK] path/name varies between SDK versions
ELF := yahbs-ps5.elf
all: $(ELF)
$(ELF): $(SRC)
	$(CC) $(CFLAGS) $^ $(LDLIBS) -o $@
clean:; rm -f $(ELF)
