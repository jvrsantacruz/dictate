# dictate. The shipped artifact is a single zipapp on the system interpreter,
# packaged as a deb; the venv here exists only for the linters and the unit
# tests. The two other test tiers run on the system interpreter, which has
# `gi`: see docs/development.md.

PYTHON   ?= /usr/bin/python3
ARTIFACT  = dist/dictate
STAGE     = build/zipapp
TOOLS     = ../tools
# Outside a git checkout, such as a release tarball: make VERSION=X.Y.Z SOURCE_DATE_EPOCH=N deb
ifeq ($(origin VERSION),undefined)
VERSION := $(shell $(TOOLS)/deb-version v .)
endif
DEB       = dist/dictate_$(VERSION)_all.deb
ROOT      = build/deb

.DEFAULT_GOAL := help
.PHONY: help build deb deb-check lint test integration smoke run clean

## help         this list
help:
	@sed -n 's/^## //p' $(firstword $(MAKEFILE_LIST))

## build        pack src/ into $(ARTIFACT). Same source, same bytes, so a rebuild with no
##              change gives an identical file.
##
## Staged rather than packed from src/, for the reasons in
## ../dictate-indicator/Makefile: one fixed time, fixed modes, UTC, and only
## the source, so byte code and editor files stay out. The interpreter is
## named, not looked up: IBus runs the engine with ~/.local/bin first on PATH,
## and a python installed there by uv has no `gi`.
build:
	@rm -rf $(STAGE)
	@mkdir -p $(STAGE) dist
	cd src && cp --parents $$(find dictate -name '*.py') $(CURDIR)/$(STAGE)/
	cp src/dictate/__main__.py $(STAGE)/__main__.py
	@chmod -R u=rwX,go=rX $(STAGE)
	@find $(STAGE) -exec touch -h -d @946684800 {} +
	TZ=UTC $(PYTHON) -m zipapp $(STAGE) \
		--python "$(PYTHON)" \
		--output $(ARTIFACT)
	@chmod +x $(ARTIFACT)
	@ls -l $(ARTIFACT)

## deb          the apt package, $(DEB). Same source and same build tools
##              (dpkg-deb, xz, gzip, python), same bytes; the version moves
##              with every change
deb: build
	@rm -rf $(ROOT) dist/dictate_*.deb
	install -Dm755 $(ARTIFACT) $(ROOT)/usr/bin/dictate
	install -Dm755 data/dictate-status $(ROOT)/usr/bin/dictate-status
	install -Dm755 data/dictate.tmux $(ROOT)/usr/share/dictate/dictate.tmux
	install -d $(ROOT)/usr/share/ibus/component
	$(ARTIFACT) component /usr/bin/dictate $(VERSION) > $(ROOT)/usr/share/ibus/component/dictate.xml
	install -Dm644 packaging/dictate.1 $(ROOT)/usr/share/man/man1/dictate.1
	install -Dm644 packaging/dictate-status.1 $(ROOT)/usr/share/man/man1/dictate-status.1
	install -Dm644 packaging/copyright $(ROOT)/usr/share/doc/dictate/copyright
	VERSION=$(VERSION) $(TOOLS)/deb-build $(ROOT) packaging/control $(DEB)

## deb-check    lintian, then install, reinstall and remove the package in a
##              clean container of each supported Ubuntu
deb-check: deb
	$(TOOLS)/deb-check $(DEB)

## lint         ruff and vulture
lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run vulture

## test         the unit tier: pure rules, no desktop
test:
	uv run pytest -q

## integration  the headless tier: a private GNOME Shell, never this desktop
integration: build
	tests/integration/run $(CURDIR)/$(ARTIFACT)

## smoke        the live tier: this desktop, ydotool. Takes the keyboard for
##              about 20 seconds; the screen must be unlocked
smoke:
	$(PYTHON) tests/integration/smoke.py /usr/bin/dictate

## clean        remove the build output
clean:
	rm -rf dist build
