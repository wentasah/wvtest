
all: build
	@echo
	@echo "Try: make test"

VERSION=$(shell git describe --always --match='v[0-9]')

wvtool: wvtool.py FORCE
	python3 $< format sample-ok # Quick syntax check
	sed -e '/^version = .*/ s//version = "$(VERSION)"/' $< > $@
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


test: build
	./wvtool run $(MAKE) runtests

clean::
	rm -f *~ .*~
	$(MAKE) -C sh clean
	$(MAKE) -C python clean
	$(MAKE) -C dotnet clean
	$(MAKE) -C cpp clean
	$(MAKE) -C c clean
