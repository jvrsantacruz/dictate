# The four packages, built and checked together.

APPS = dictate dictate-indicator dictate-uinput dictate-whisper
# Packages that install only where their dependencies exist: whisper.cpp is in
# Ubuntu from 26.04.
ONLY_ON = dictate-whisper=26.04

.DEFAULT_GOAL := help
.PHONY: help lint test deb deb-check clean

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

## deb        the four packages, into each app's dist/
deb:
	for app in $(APPS); do $(MAKE) -C $$app deb || exit 1; done

## deb-check  lintian, then upgrade, reinstall and purge in clean Ubuntu containers
deb-check: deb
	ONLY_ON="$(ONLY_ON)" tools/deb-check $(foreach app,$(APPS),$(wildcard $(app)/dist/*.deb))

## clean      remove every build output
clean:
	for app in $(APPS); do $(MAKE) -C $$app clean; done
