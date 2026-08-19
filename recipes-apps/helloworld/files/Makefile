CC ?= $(CROSS_COMPILE)gcc
CFLAGS ?= -O2 -Wall
LDFLAGS ?= 

all:
	$(CC) $(CFLAGS) hello.c -o hello $(LDFLAGS)

clean:
	rm -f hello
