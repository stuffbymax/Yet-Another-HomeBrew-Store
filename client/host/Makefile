CFLAGS ?= -O2 -Wall -Wextra -DYAHBS_ALLOW_HTTP   # remove the define for release builds
all: yahbs_host
yahbs_host: main_host.c platform_host.c ../common/yahbs.c ../common/sha256.c
	$(CC) $(CFLAGS) -o $@ $^ -lcurl
clean:
	rm -f yahbs_host
