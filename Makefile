
all: build
	@echo
	@echo "Try: make test"

VERSION=$(shell git describe --dirty --always --match='v[0-9]')

wvtool: wvtool.py FORCE
	python3 -m py_compile $< # Syntax check
	python3 $< format sample-ok # Quick functionality check
	sed -e '/^version = .*/ s//version = "$(VERSION)"/' -e '/# compile-command: "make wvtool"/d' $< > $@
	chmod +x $@

FORCE:

build: wvtool
	$(MAKE) -C dotnet all
	$(MAKE) -C cpp all
	$(MAKE) -C c all

runtests: build
	$(MAKE) -C sh runtests
	$(MAKE) -C python runtests
	$(MAKE) -C dotnet runtests
	$(MAKE) -C cpp runtests
	$(MAKE) -C c runtests
	$(MAKE) -C javascript runtests


test: build
	./wvtool run $(MAKE) runtests

clean::
	rm -f *~ .*~
	$(MAKE) -C sh clean
	$(MAKE) -C python clean
	$(MAKE) -C dotnet clean
	$(MAKE) -C cpp clean
	$(MAKE) -C c clean
