# dictate-uinput: one udev rule, packaged alone so installing it is the
# admin's consent to the grant.

TOOLS    = ../tools
# Built outside the checkout, never in it: the repository holds sources only.
# OUT moves it; debian/rules points it inside its own build tree.
OUT     ?= $(or $(XDG_CACHE_HOME),$(HOME)/.cache)/dictate/dictate-uinput
# Outside a git checkout, such as a release tarball: make VERSION=X.Y.Z SOURCE_DATE_EPOCH=N deb
ifeq ($(origin VERSION),undefined)
VERSION := $(shell $(TOOLS)/deb-version v .)
endif
DEB      = $(OUT)/dist/dictate-uinput_$(VERSION)_all.deb
ROOT     = $(OUT)/build/deb

.DEFAULT_GOAL := help
.PHONY: help stage deb deb-path deb-check clean

## help       this list
help:
	@sed -n 's/^## //p' $(firstword $(MAKEFILE_LIST))

## deb        the apt package, $(DEB)
## stage        the installed files under $(ROOT); the scripts are packaging/'s
stage:
	@rm -rf $(ROOT)
	install -Dm644 data/72-dictate-uinput.rules $(ROOT)/usr/lib/udev/rules.d/72-dictate-uinput.rules
	install -Dm644 packaging/copyright $(ROOT)/usr/share/doc/dictate-uinput/copyright
	install -Dm644 packaging/lintian-overrides $(ROOT)/usr/share/lintian/overrides/dictate-uinput

deb: stage
	@rm -f $(OUT)/dist/dictate-uinput_*.deb
	install -Dm755 packaging/postinst $(ROOT)/DEBIAN/postinst
	install -Dm755 packaging/postrm $(ROOT)/DEBIAN/postrm
	VERSION=$(VERSION) $(TOOLS)/deb-build $(ROOT) packaging/control $(DEB)

## deb-path   where make deb writes this version's package
deb-path:
	@echo $(DEB)

## deb-check  lintian, then upgrade, reinstall and purge in clean containers
deb-check: deb
	$(TOOLS)/deb-check $(DEB)

## clean      remove the build output
clean:
	rm -rf $(OUT)/dist $(OUT)/build
