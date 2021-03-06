#!/usr/bin/env python3

# Copyright 2014, 2015, 2017 Michal Sojka <sojkam1@fel.cvut.cz>
# License: GPLv2+

"""Versatile WvTest protocol tool. It replaces wvtestrun script and
provides some other useful features. Namely:
- Summary mode (--summary)
- Test results aligned to the same column
- (Experimental) Export to JUnit XML
- TODO: Conversion to HTML
- TODO: Variable timeout
- TODO: Checking of expected number of tests

Newest version can be found at https://github.com/wentasah/wvtest.
"""

version = "git"  # This gets repaced by make

import argparse
import subprocess as sp
import re
import sys
import os
import signal
import math
import io
import datetime
import time
import socket

# Regulr expression that matches potential prefixes to wvtest protocol lines
re_prefix = ''

class Term:
    class attr:
        reset         = '\033[0m'
        bold          = '\033[01m'
        disable       = '\033[02m'
        underline     = '\033[04m'
        reverse       = '\033[07m'
        strikethrough = '\033[09m'
        invisible     = '\033[08m'
    class fg:
        black      = '\033[30m'
        red        = '\033[31m'
        green      = '\033[32m'
        orange     = '\033[33m'
        blue       = '\033[34m'
        purple     = '\033[35m'
        cyan       = '\033[36m'
        lightgrey  = '\033[37m'
        darkgrey   = '\033[1;30m'
        lightred   = '\033[1;31m'
        lightgreen = '\033[1;32m'
        yellow     = '\033[1;33m'
        lightblue  = '\033[1;34m'
        pink       = '\033[1;35m'
        lightcyan  = '\033[1;36m'
    class bg:
        black     = '\033[40m'
        red       = '\033[41m'
        green     = '\033[42m'
        orange    = '\033[43m'
        blue      = '\033[44m'
        purple    = '\033[45m'
        cyan      = '\033[46m'
        lightgrey = '\033[47m'

    progress_chars = '|/-\\'

    def __init__(self, width=None):
        if not 'TERM'  in os.environ or os.environ['TERM'] == 'dumb':
            self.output = None
        else:
            try:
                self.output = open('/dev/tty', 'w')
            except IOError:
                self.output = None

        self.width = width or self._get_width()
        self._enabled = True
        self._progress_msg = ''
        self._progress_idx = 0

    def _raw_write(self, string):
        '''Write raw data if output is enabled.'''
        if self._enabled and self.output:
            try:
                self.output.write(string)
                self.output.flush()
            except IOError:
                self._enabled = False

    def _get_width(self):
        try:
            import fcntl, termios, struct, os
            s = struct.pack('HHHH', 0, 0, 0, 0)
            x = fcntl.ioctl(self.output.fileno(), termios.TIOCGWINSZ, s)
            width = struct.unpack('HHHH', x)[1]
            if width <= 0:
                raise Exception
            return width
        except:
            return int(getattr(os.environ, 'COLUMNS', 80))

    def clear_colors(self):
        '''Sets all color and attribute memebers to empty strings'''
        for cls in ('attr', 'fg', 'bg'):
            c = getattr(self, cls)
            for key in dir(c):
                if key[0] == '_':
                    continue
                setattr(c, key, '')

    def set_progress_msg(self, msg):
        self._progress_msg = msg
        self._progress_idx = 0
        self.update_progress_msg()

    def update_progress_msg(self):
        self._progress_idx += 1
        if self._progress_idx >= len(self.progress_chars):
            self._progress_idx = 0
        if self.output:
            self._raw_write(self._progress_msg[:self.width - 3] + " " + self.progress_chars[self._progress_idx] + "\r")

    def clear_progress_msg(self):
        if self.output:
            self._raw_write(' '*(len(self._progress_msg[:self.width - 3]) + 2) + "\r")


class WvLine:
    def __init__(self, match):
        for (key, val) in match.groupdict().items():
            setattr(self, key, val)

    def print(self, file=sys.stdout):
        "Print the line (terminal is expected on output)"
        print(str(self), file=file)

    def log(self, file=sys.stdout):
        "Print the line (without terminal escape sequences)"
        self.print(file)


class WvPlainLine(WvLine):
    re = re.compile("(?P<line>.*)")

    def __str__(self):
        return self.line

class WvTestingLine(WvLine):
    re = re.compile('(?P<prefix>' + re_prefix + ')Testing "(?P<what>.*)" in (?P<where>.*):$')

    def __init__(self, *args):
        if len(args) == 1:
            WvLine.__init__(self, args[0])
        elif len(args) == 2:
            self.prefix = ''
            self.what = args[0]
            self.where = args[1]
        else:
            raise TypeError("WvTestingLine.__init__() takes at most 2 positional arguments")

    def __str__(self):
        return '{self.prefix}Testing "{self.what}" in {self.where}:'.format(self=self)

    def print(self, file=sys.stdout):
        print(term.attr.bold + str(self) + term.attr.reset, file=file)

    def log(self, file):
        print(str(self), file=file)

    def asWvCheckLine(self, result):
        return WvCheckLine('{self.where}  {self.what}'.format(self=self), result)

class WvCheckLine(WvLine):
    re = re.compile('(?P<prefix>' + re_prefix + ')!\s*(?P<text>.*?)\s+(?P<result>\S+)$')

    def __init__(self, *args):
        if len(args) == 1:
            WvLine.__init__(self, args[0])
        elif len(args) == 2:
            self.prefix = ''
            self.text = args[0].rstrip(' .')
            self.result = args[1]
        else:
            raise TypeError("WvCheckLine.__init__() takes at most 2 positional arguments")

    def __str__(self):
        # Result == None when printing progress message
        return '{self.prefix}! {self.text} {result}'.format(self=self, result=(self.result or ''))

    def is_success(self):
        return self.result == 'ok'

    def formated(self, highlight=True, include_newlines=False, result_space=10):
        text = '{self.prefix}! {self.text} '.format(self=self)
        if highlight:
            if self.is_success():
                color = term.fg.lightgreen
            else:
                color = term.fg.lightred

            result = term.attr.bold + color + self.result + term.attr.reset
            width = term.width
        else:
            result = self.result
            width = 80

        lines = math.ceil((len(text) + result_space) / width)
        text = format(text, '.<' + str(lines * width - result_space))
        if include_newlines:
            for i in reversed(range(width, width*lines, width)):
                text = text[:i] + '\n' + text[i:]
        return '{text} {result}'.format(text=text, result=result)

    def print(self, file=sys.stdout):
        print(self.formated(), file=file)

    def log(self, file=sys.stdout):
        text = '{self.prefix}! {self.text} '.format(self=self)
        print('{text:.<80} {result}'.format(text=text, result=self.result), file=file)


class WvTagLine(WvLine):
    re  = re.compile('(?P<prefix>' + re_prefix + ')wvtest:\s*(?P<tag>.*)$')

class WvTestProcessor(list):

    class Verbosity:
        # Print one line for each "Testing" section. Passed tests are
        # printed as "ok", failed tests as "FAILURE".
        SUMMARY = 1

        # Print one "ok" line for each passing "Testing" section.
        # Failed "Testing" sections are printed verbosely.
        NORMAL  = 2

        # Print every line of the output, just
        # reformat/syntax-highlight known lines.
        VERBOSE = 3

    def __init__(self,
                 verbosity = Verbosity.NORMAL,
                 junit_xml: io.IOBase = None,
                 junit_prefix: str = '',
                 logdir = None):
        self.checkCount = 0
        self.checkFailedCount = 0
        self.testCount = 0
        self.testFailedCount = 0

        self.implicitTestTitle = None
        self.currentTest = None

        self.verbosity = verbosity
        self.show_progress = False

        self.junit_xml = junit_xml
        self.junit_prefix = junit_prefix

        if junit_xml:
            global wvjunit
            import wvjunit
            self.junitTestcases = []
            self.junitTestsuites = []

        self.logdir = logdir
        self.log = None
        if logdir and not os.path.isdir(logdir):
            os.mkdir(logdir)

    def setImplicitTestTitle (self, testing):
        """If the test does not supply its own title as the first line of test
        output, this title will be used instead."""
        self.implicitTestTitle = testing

    def print(self, file=sys.stdout):
        for entry in self:
            entry.print(file=file)

    def __str__(self):
        s = ''
        for entry in self:
            if 'formated' in dir(entry):
                e = entry.formated()
            else:
                e = str(entry)
            s += e + "\n"
        return s

    def plainText(self):
        return "\n".join([str(entry) for entry in self]) + "\n"

    def _rememberJUnitTestcase(self, check: WvCheckLine):
        if not self.junit_xml:
            return

        t = time.time()
        duration = t - (self.lastCheckTime or self.testStartTime)
        self.lastCheckTime = t

        if not check.is_success():
            failure = wvjunit.Failure(type='WvTest check',
                                      message=check.text)
        else:
            failure = None

        self.junitTestcases.append(
            wvjunit.Testcase(
                classname="{}{}.{}".format(
                    self.junit_prefix,
                    self.currentTest.where.replace('.', '_'),
                    self.currentTest.what),
                name=check.text,
                time=duration,
                failure=failure))

    def _rememberJUnitTestsuite(self):
        if not self.junit_xml:
            return

        system_out = wvjunit.SystemOut(text=self.plainText())

        ts = wvjunit.Testsuite(tests=self.checkCount,
                               failures=self.checkFailedCount,
                               errors=0,
                               name="{}{}.{}".format(
                                   self.junit_prefix,
                                   self.currentTest.where.replace('.', '_'),
                                   self.currentTest.what),
                               time=time.time()-self.testStartTime,
                               hostname=socket.getfqdn(),
                               timestamp=datetime.datetime.now(),
                               testcases=self.junitTestcases,
                               system_out=system_out)
        self.junitTestsuites.append(ts)
        self.junitTestcases = []

    def _generateJUnitXML(self):
        if not self.junit_xml:
            return
        tss = wvjunit.Testsuites(testsuites=self.junitTestsuites)
        tss.print(file=self.junit_xml)

    def _finishCurrentTest(self):
        self._rememberJUnitTestsuite()
        if self.checkFailedCount > 0:
            if self.show_progress and self.verbosity < self.Verbosity.VERBOSE:
                term.clear_progress_msg()
            if self.verbosity == self.Verbosity.NORMAL:
                self.print()
            elif self.verbosity < self.Verbosity.NORMAL:
                self.currentTest.asWvCheckLine('FAILED').print()
            self.testFailedCount += 1
        else:
            if self.verbosity <= self.Verbosity.NORMAL:
                self.currentTest.asWvCheckLine('ok').print()
        sys.stdout.flush()
        self.clear()
        if self.log:
            self.log.close()

    def clear(self):
        del self[:]

    def _newTest(self, testing : WvTestingLine):
        if self.currentTest:
            self._finishCurrentTest()
        if testing != None:
            self.testCount += 1
            if self.show_progress and self.verbosity < self.Verbosity.VERBOSE:
                term.set_progress_msg(str(testing.asWvCheckLine(None)))

            if self.logdir:
                trans = str.maketrans(' /', '__')
                self.log = open(os.path.join(self.logdir, "%04d-%s-%s.log" %
                                             (self.testCount,
                                              testing.where.translate(trans),
                                              testing.what.lower().translate(trans))),
                                'w')
            self.testStartTime = time.time()
            self.lastCheckTime = None
        self.currentTest = testing
        self.checkCount = 0
        self.checkFailedCount = 0

    def _newCheck(self, check: WvCheckLine):
        self.checkCount += 1
        if not check.is_success():
            self.checkFailedCount += 1
        self._rememberJUnitTestcase(check)

    def append(self, logEntry: WvLine):
        if self.implicitTestTitle:
            if str(logEntry) == '':
                pass
            elif type(logEntry) != WvTestingLine:
                self._newTest(self.implicitTestTitle)
                super().append(self.implicitTestTitle)
                self.implicitTestTitle = None
            else:
                self.implicitTestTitle = None


        if type(logEntry) == WvTestingLine:
            self._newTest(logEntry)
        elif type(logEntry) == WvCheckLine:
            self._newCheck(logEntry)

        list.append(self, logEntry)

        if self.verbosity == self.Verbosity.VERBOSE:
            logEntry.print()
        else:
            if self.show_progress:
                term.update_progress_msg()

        if self.log:
            logEntry.log(self.log)

    def processLine(self, line):
        line = line.rstrip()
        logEntry = None

        for lineClass in [ WvCheckLine, WvTestingLine, WvTagLine, WvPlainLine ]:
            match = lineClass.re.match(line)
            if match:
                logEntry = lineClass(match)
                break
        if not logEntry:
            raise Exception("Non-matched line: {}".format(line))

        self.append(logEntry)

    def done(self):
        self._newTest(None)

        self._generateJUnitXML()

        print("WvTest: {total} test{plt}, {fail} failure{plf}."
              .format(total = self.testCount, plt = '' if self.testCount == 1 else 's',
                      fail = self.testFailedCount, plf = '' if self.testFailedCount  == 1 else 's'))
    def is_success(self):
        return self.testFailedCount == 0

def _run(command, processor, timeout=100):
    processor.show_progress = True


    def kill_child(sig = None, frame = None):
        os.killpg(proc.pid, sig)

    def alarm(sig = None, frame = None):
        msg = "! {wvtool}: Alarm timed out!  No test output for {timeout} seconds.  FAILED"
        processor.processLine(msg.format(wvtool=sys.argv[0], timeout=timeout))
        kill_child(signal.SIGTERM)

    signal.signal(signal.SIGINT, kill_child)
    signal.signal(signal.SIGTERM, kill_child)
    signal.signal(signal.SIGALRM, alarm)

    cmd = command if isinstance(command, str) else ' '.join(command)
    processor.setImplicitTestTitle(WvTestingLine("Preamble of "+cmd, "wvtool"))

    # Popen does not seem to be able to call setpgrp(). Therefore, we
    # use start_new_session, but this also create a new session and
    # detaches the process from a terminal. This might be a problem
    # for programs that need a terminal to run.
    with sp.Popen(command, stdin=None, stdout=sp.PIPE, stderr=sp.STDOUT,
                  universal_newlines=False, start_new_session=True) as proc:
        signal.alarm(timeout)
        stdout = io.TextIOWrapper(proc.stdout, errors='replace')
        for line in stdout:
            signal.alarm(timeout)
            processor.processLine(line)

    signal.alarm(0)

    if proc.returncode != 0:
        if proc.returncode > 0:
            msg = "{wvtool}: Program '{cmd}' returned non-zero exit code {ec}"
        else:
            msg = "{wvtool}: Program '{cmd}' terminated by signal {sig}"

        text = msg.format(wvtool=sys.argv[0], cmd=cmd,
                          ec=proc.returncode, sig=-proc.returncode)
        processor.append(WvCheckLine(text, 'FAILED'))

def do_run(args, processor):
    _run(args.command, processor, timeout=args.timeout)

def do_runall(args, processor):
    for cmd in args.commands:
        _run(cmd, processor)

def do_format(args, processor):
    files = args.infiles
    if len(files) == 0:
        processor.setImplicitTestTitle(WvTestingLine("Preamble", "stdin"))
        for line in io.TextIOWrapper(sys.stdin.buffer, errors='replace'):
            processor.processLine(line)
    else:
        for fn in args.infiles:
            processor.setImplicitTestTitle(WvTestingLine("Preamble", fn))
            for line in open(fn, errors='replace'):
                processor.processLine(line)

def do_wrap(args, processor):
    pass

parser = argparse.ArgumentParser(description='Versatile wvtest tool')


parser.set_defaults(verbosity=WvTestProcessor.Verbosity.NORMAL)
parser.add_argument('-v', '--verbose', dest='verbosity', action='store_const',
                    const=WvTestProcessor.Verbosity.VERBOSE,
                    help='Do not hide output of successful tests')
parser.add_argument('-s', '--summary', dest='verbosity', action='store_const',
                    const=WvTestProcessor.Verbosity.SUMMARY,
                    help='''Hide output of all tests. Print just one line for each "Testing"
                    section and report "ok" or "FAILURE" of it.''')
parser.add_argument('-w', '--width', type=int,
                    help='Override terminal width or COLUMNS environment wariable.')
parser.add_argument('--timeout', type=int, default=100, metavar='SEC',
                    help='Timeout in seconds for any test output (default %(default)s)')
parser.add_argument('--junit-xml', type=argparse.FileType('w'), metavar='FILE',
                    help='''Convert output to JUnit compatible XML file''')
parser.add_argument('--junit-prefix', metavar='STR',
                    help='''Prefix to prepend to generated class names (useful when a test is
                    run multiple times in different environments)''')
parser.add_argument('--logdir', metavar='DIR',
                    help='''Store test logs in the given directory''')
parser.add_argument('--color', action='store_true', default=None,
                    help='Force color output')
parser.add_argument('--no-color', action='store_false', dest='color',
                    help='Disable color output')

parser.add_argument('--version', action='version', version='%(prog)s '+version)

subparsers = parser.add_subparsers(help='sub-command help')

parser_run = subparsers.add_parser('run', help='Run and supervise a command producing wvtest output')
parser_run.add_argument('command', nargs=argparse.REMAINDER, help='Command to run')
parser_run.set_defaults(func=do_run)

parser_runall = subparsers.add_parser('runall', help='Run multiple scripts/binaries mentioned on command line')
parser_runall.set_defaults(func=do_runall)
parser_runall.add_argument('commands', nargs='+', help='Scripts/binaries to run')

parser_format = subparsers.add_parser('format', help='Reformat/highlight/summarize WvTest protocol output')
parser_format.set_defaults(func=do_format)
parser_format.add_argument('infiles', nargs='*', help='Files with wvtest output')

# parser_wrap = subparsers.add_parser('wrap')
# parser_wrap.set_defaults(func=do_wrap)

args = parser.parse_args()
term = Term(args.width)
if args.color is None and not term.output or \
   args.color is False:
    term.clear_colors()

if not 'func' in args:
    parser.print_help()
    sys.exit(1)

processor = WvTestProcessor(
    args.verbosity,
    junit_xml = args.junit_xml,
    junit_prefix = args.junit_prefix,
    logdir=args.logdir)
args.func(args, processor)
processor.done()
sys.exit(0 if processor.is_success() else 1)

# Local Variables:
# compile-command: "make wvtool"
# End:
