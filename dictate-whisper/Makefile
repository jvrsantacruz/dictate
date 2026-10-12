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
# Silero's voice activity model, which the server cuts speech with, so a 15 s
# audio window holds every piece: a third of the time of whisper's 30 s.
VAD            = ggml-silero-v5.1.2.bin
VAD_REVISION   = 9ffd54a1e1ee413ddf265af9913beaf518d1639b
VAD_SHA256     = 29940d98d42b91fbd05ce489f3ecf7c72f0a42f027e4875919a28fb4c04ea2cf
VAD_URL        = https://huggingface.co/ggml-org/whisper-vad/resolve/$(VAD_REVISION)/$(VAD)
VAD_CACHE      = cache/$(VAD)

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

$(VAD_CACHE):
	@mkdir -p cache
	curl -fsSL --retry 3 -o $@.part $(VAD_URL)
	echo "$(VAD_SHA256)  $@.part" | sha256sum -c --quiet || { rm -f $@.part; exit 1; }
	mv $@.part $@

## deb        the apt package, $(DEB)
deb: $(CACHE) $(VAD_CACHE)
	@rm -rf $(ROOT) dist/dictate-whisper_*.deb
	echo "$(MODEL_SHA256)  $(CACHE)" | sha256sum -c --quiet
	echo "$(VAD_SHA256)  $(VAD_CACHE)" | sha256sum -c --quiet
	install -Dm644 $(CACHE) $(ROOT)/usr/share/dictate-whisper/$(MODEL)
	install -Dm644 $(VAD_CACHE) $(ROOT)/usr/share/dictate-whisper/$(VAD)
	install -Dm644 data/dictate-whisper.service $(ROOT)/usr/lib/systemd/user/dictate-whisper.service
	install -Dm644 packaging/copyright $(ROOT)/usr/share/doc/dictate-whisper/copyright
	install -Dm644 packaging/lintian-overrides $(ROOT)/usr/share/lintian/overrides/dictate-whisper
	@mkdir -p $(ROOT)/DEBIAN
	sed -e 's|@UNITS@|dictate-whisper.service|' -e 's|@ONLY_WITH@||' $(TOOLS)/postinst-restart > $(ROOT)/DEBIAN/postinst
	VERSION=$(VERSION) $(TOOLS)/deb-build $(ROOT) packaging/control $(DEB)

## deb-check  lintian, then upgrade, reinstall and purge in clean containers
deb-check: deb
	ONLY_ON="dictate-whisper=26.04" $(TOOLS)/deb-check $(DEB)

## clean      remove the build output; the model stays in cache/
clean:
	rm -rf dist build
