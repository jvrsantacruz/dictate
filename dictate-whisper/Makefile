# dictate-whisper: a local transcriber for dictate. whisper.cpp from Ubuntu,
# the base model fetched at a pinned revision and checked, and a user unit.

TOOLS    = ../tools
# Outside a git checkout, such as a release tarball: make VERSION=X.Y.Z SOURCE_DATE_EPOCH=N deb
ifeq ($(origin VERSION),undefined)
VERSION := $(shell $(TOOLS)/deb-version v .)
endif
DEB      = dist/dictate-whisper_$(VERSION)_all.deb
ROOT     = build/deb
# Pinned: a revision of the model repository and the file's hash, so the same
# source gives the same package. Raising either is a release of its own.
MODEL          = ggml-base-q5_1.bin
MODEL_REVISION = 5359861c739e955e79d9a303bcbc70fb988958b1
MODEL_SHA256   = 422f1ae452ade6f30a004d7e5c6a43195e4433bc370bf23fac9cc591f01a8898
MODEL_URL      = https://huggingface.co/ggerganov/whisper.cpp/resolve/$(MODEL_REVISION)/$(MODEL)
# Outside build/, so `make clean` does not throw away 60 MB to fetch again.
CACHE          = cache/$(MODEL)

.DEFAULT_GOAL := help
.PHONY: help deb deb-check clean

## help       this list
help:
	@sed -n 's/^## //p' $(firstword $(MAKEFILE_LIST))

## model      fetch the model into cache/, once; a wrong hash deletes it
$(CACHE):
	@mkdir -p cache
	curl -fsSL --retry 3 -o $@.part $(MODEL_URL)
	echo "$(MODEL_SHA256)  $@.part" | sha256sum -c --quiet || { rm -f $@.part; exit 1; }
	mv $@.part $@

## deb        the apt package, $(DEB)
deb: $(CACHE)
	@rm -rf $(ROOT) dist/dictate-whisper_*.deb
	echo "$(MODEL_SHA256)  $(CACHE)" | sha256sum -c --quiet
	install -Dm644 $(CACHE) $(ROOT)/usr/share/dictate-whisper/$(MODEL)
	install -Dm644 data/dictate-whisper.service $(ROOT)/usr/lib/systemd/user/dictate-whisper.service
	install -Dm644 packaging/copyright $(ROOT)/usr/share/doc/dictate-whisper/copyright
	VERSION=$(VERSION) $(TOOLS)/deb-build $(ROOT) packaging/control $(DEB)

## deb-check  lintian, then upgrade, reinstall and purge in clean containers
deb-check: deb
	ONLY_ON="dictate-whisper=26.04" $(TOOLS)/deb-check $(DEB)

## clean      remove the build output; the model stays in cache/
clean:
	rm -rf dist build
