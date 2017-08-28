
all:
	@echo "Try: make test"
	@false

runtests:
	t/twvtest.sh

test:
	../wvtool run t/twvtest.sh
	WV_BASE_DIR=$(CURDIR) ../wvtool run t/twvtest.sh

clean::
	rm -rf *~ t/*~ test.*
