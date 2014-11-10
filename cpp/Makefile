
all: t/wvtest

t/wvtest: wvtestmain.cc wvtest.cc t/wvtest.t.cc
	g++ -D WVTEST_CONFIGURED -o $@ -I. $^

runtests: all
	t/wvtest

test: all
	../wvtool run $(MAKE) runtests

clean::
	rm -f *~ t/*~ *.o t/*.o t/wvtest
