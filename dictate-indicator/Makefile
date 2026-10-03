# dictate-indicator. The shipped artifact is a single zipapp on the system
# interpreter; the venv here exists only for the linters and the tests.

PYTHON  ?= /usr/bin/python3
ARTIFACT = dist/dictate-indicator
STAGE    = build/zipapp
TOOLS    = ../tools
# Outside a git checkout, such as a release tarball: make VERSION=X.Y.Z SOURCE_DATE_EPOCH=N deb
ifeq ($(origin VERSION),undefined)
VERSION := $(shell $(TOOLS)/deb-version v .)
endif
DEB      = dist/dictate-indicator_$(VERSION)_all.deb
ROOT     = build/deb

.DEFAULT_GOAL := help
.PHONY: help build deb deb-check lint test run clean

## help     this list
help:
	@sed -n 's/^## //p' $(firstword $(MAKEFILE_LIST))

## build    pack src/ into $(ARTIFACT). Same source, same bytes, so a rebuild with no
##          change gives an identical file.
##
## Staged rather than packed from src/: `--main` makes zipapp write its own
## `__main__.py` stamped with the current time, and the tree's mtimes change
## with every checkout. The stage takes the package's own `__main__.py` as its
## entry point, and one fixed time. 2000, not the epoch: zip cannot store a
## date before 1980. Only the source and the icons are staged, so byte code and
## editor swap files stay out; modes are set and the time is UTC because zip
## stores both, and a umask or a timezone would otherwise change the bytes.
build:
	@rm -rf $(STAGE)
	@mkdir -p $(STAGE) dist
	cd src && cp --parents $$(find dictate_indicator -name '*.py' -o -name '*.svg') \
		$(CURDIR)/$(STAGE)/
	cp src/dictate_indicator/__main__.py $(STAGE)/__main__.py
	@chmod -R u=rwX,go=rX $(STAGE)
	@find $(STAGE) -exec touch -h -d @946684800 {} +
	TZ=UTC $(PYTHON) -m zipapp $(STAGE) \
		--python "$(PYTHON)" \
		--output $(ARTIFACT)
	@chmod +x $(ARTIFACT)
	@ls -l $(ARTIFACT)

## deb      the apt package, $(DEB)
deb: build
	@rm -rf $(ROOT) dist/dictate-indicator_*.deb
	install -Dm755 $(ARTIFACT) $(ROOT)/usr/bin/dictate-indicator
	install -Dm644 data/dictate-indicator.service \
		$(ROOT)/usr/lib/systemd/user/dictate-indicator.service
	install -Dm644 packaging/dictate-indicator.1 \
		$(ROOT)/usr/share/man/man1/dictate-indicator.1
	install -Dm644 packaging/copyright $(ROOT)/usr/share/doc/dictate-indicator/copyright
	VERSION=$(VERSION) $(TOOLS)/deb-build $(ROOT) packaging/control $(DEB)

## deb-check  lintian, install, reinstall and remove in clean containers
deb-check: deb
	$(TOOLS)/deb-check $(DEB)

## lint     ruff and vulture
lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run vulture

## test     the whole suite
test:
	uv run pytest -q

## run      run from the source tree, on the system interpreter
run:
	PYTHONPATH=src $(PYTHON) -m dictate_indicator --verbose

## clean    remove the build output
clean: clean-cache
	rm -rf dist build

.PHONY: clean-cache
clean-cache:
	@find src \( -name __pycache__ -o -name '*.egg-info' \) -prune \
		-exec rm -rf {} + 2>/dev/null || true
