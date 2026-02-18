# Makefile for landlock_sandboxer.so
#
# Build: make
# Install: sudo make install
# Clean: make clean

CC       ?= gcc
CFLAGS   ?= -O2 -Wall -Wextra -Werror -pedantic
LDFLAGS  ?= -shared
TARGET   = landlock_sandboxer.so
SRC      = landlock_sandboxer.c
DESTDIR  ?= /opt/aegish/lib

.PHONY: all install clean

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -fPIC $(LDFLAGS) -o $@ $<

install: $(TARGET)
	install -d $(DESTDIR)
	install -m 0644 $(TARGET) $(DESTDIR)/$(TARGET)

clean:
	rm -f $(TARGET)
