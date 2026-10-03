# dictate-uinput: one udev rule, packaged alone so installing it is the
# admin's consent to the grant.

TOOLS    = ../tools
VERSION := $(shell $(TOOLS)/deb-version v .)
DEB      = dist/dictate-uinput_$(VERSION)_all.deb
ROOT     = build/deb

.DEFAULT_GOAL := help
.PHONY: help deb deb-check clean

## help       this list
help:
	@sed -n 's/^## //p' $(firstword $(MAKEFILE_LIST))

## deb        the apt package, $(DEB)
deb:
	@rm -rf $(ROOT) dist/dictate-uinput_*.deb
	install -Dm644 data/72-dictate-uinput.rules $(ROOT)/usr/lib/udev/rules.d/72-dictate-uinput.rules
	install -Dm644 packaging/copyright $(ROOT)/usr/share/doc/dictate-uinput/copyright
	install -Dm644 packaging/lintian-overrides $(ROOT)/usr/share/lintian/overrides/dictate-uinput
	install -Dm755 packaging/postinst $(ROOT)/DEBIAN/postinst
	install -Dm755 packaging/postrm $(ROOT)/DEBIAN/postrm
	VERSION=$(VERSION) $(TOOLS)/deb-build $(ROOT) packaging/control $(DEB)

## deb-check  lintian, then upgrade, reinstall and purge in clean containers
deb-check: deb
	$(TOOLS)/deb-check $(DEB)

## clean      remove the build output
clean:
	rm -rf dist build
