# The four packages, built and checked together.

APPS = dictate dictate-indicator dictate-uinput dictate-whisper
# Packages that install only where their dependencies exist: whisper.cpp is in
# Ubuntu from 26.04.
ONLY_ON = dictate-whisper=26.04
# Each package is built outside the checkout; its Makefile says where.
deb_of = $(shell MAKEFLAGS= $(MAKE) -s --no-print-directory -C $(1) deb-path)
DEBS = $(foreach app,$(APPS),$(call deb_of,$(app)))

.DEFAULT_GOAL := help
.PHONY: help lint test deb deb-check deb-battery ppa-check clean

## help       this list
help:
	@sed -n 's/^## //p' $(firstword $(MAKEFILE_LIST))

## lint       ruff and vulture on both Python apps, shellcheck on the scripts
lint:
	$(MAKE) -C dictate lint
	$(MAKE) -C dictate-indicator lint
	shellcheck $$(find tools -type f) dictate/data/dictate-status dictate/data/dictate.tmux dictate/tests/integration/run dictate/tests/fakes/*
	shellcheck -s sh dictate-uinput/packaging/postinst dictate-uinput/packaging/postrm

## test       the unit tests of both Python apps
test:
	$(MAKE) -C dictate test
	$(MAKE) -C dictate-indicator test

## deb        the four packages, each under its OUT, outside the checkout
deb:
	for app in $(APPS); do $(MAKE) -C $$app deb || exit 1; done

## deb-check  lintian, then upgrade, reinstall and purge in clean Ubuntu containers
deb-check: deb
	ONLY_ON="$(ONLY_ON)" tools/deb-check $(DEBS)

## deb-battery  the generic deb battery: maintainer-script failure paths, per package
deb-battery: deb
	tools/deb-battery.sh --docker ubuntu:24.04 --docker ubuntu:26.04 \
	  $(foreach app,$(filter-out dictate-whisper,$(APPS)),$(call deb_of,$(app)))
	tools/deb-battery.sh --docker ubuntu:26.04 $(call deb_of,dictate-whisper)

## ppa-check  the Launchpad source package of the last tag, and the packages
##            built from it alone in a clean container of each Ubuntu
ppa-check:
	tools/ppa-check

## clean      remove every build output
clean:
	for app in $(APPS); do $(MAKE) -C $$app clean; done
