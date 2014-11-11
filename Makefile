
all: build
	@echo
	@echo "Try: make test"

wvtool: wvtool.py FORCE
	sed -e '' $< > $@
	chmod +x $@
	./$@ format sample-ok sample-error # Quick syntax error check

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
