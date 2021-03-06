"""Helper file for wvtool to export the results as JUnit compatible XML.

This file is only required when JUnit XML output is to be generated
with --junit-xml switch. Without this switch, wvtool works even when
this file is not present.

Initially, the created JUnit XML file was structured according to
http://windyroad.com.au/dl/Open%20Source/JUnit.xsd, but later, a more
meaningful structure (i.e. <system-out/> unside <testcase/>)
compatible with Jenkins JUnit plugin was implemented.
"""

import datetime
import types
import inspect
import sys
from xml.sax.saxutils import escape, quoteattr

escEntities = dict([(chr(i), "&#%d;"%i) for i in range(1, 32) if i not in [ord("\t"), ord("\n"), ord("\r")]])

# Null character is not alowed in XML document. Remove it.
escEntities['\x00'] = ''

class JUnitBase:
    def _get_valid_members(self):
        return [x for x in dir(self.__class__)
                if not x.startswith('_') and
                   not inspect.isfunction(getattr(self.__class__, x))]

    def __init__(self, **kwargs):
        """Initialize the object with kwargs as specified by class variables."""
        valid_members = self._get_valid_members()
        for (key, val) in kwargs.items():
            if key in valid_members:
                if type(val) == getattr(self.__class__, key) or val == None:
                    v = val
                else:
                    try:
                        v = getattr(self.__class__, key).__call__(val) # Construct the right type
                    except Exception as exc:
                        raise Exception("Cannot construct '{}' from '{}'".format(key, val)) from  exc
                setattr(self, key, v)
            else:
                raise(Exception("'{key}' is not a valid member of '{cls}'".format(key=key, cls=self.__class__.__name__)))

        for key in valid_members:
            if key not in kwargs:
                setattr(self, key, getattr(self.__class__, key).__call__())

    def escaped_values(self):
        class EscapedObject(object): pass
        ret = EscapedObject()
        for attr in self._get_valid_members():
            if type(getattr(self, attr)) not in [float]:
                # Encode each attribute in two ways - for use in text
                # nodes and for use in attributes.
                setattr(ret, attr, escape(str(getattr(self, attr)), escEntities))
                setattr(ret, attr+"_attr", quoteattr(str(getattr(self, attr)), escEntities))
            else:
                setattr(ret, attr, getattr(self, attr))
        return ret

    def print(self, file=sys.stdout):
        if str(self):
            print(str(self), file=file)

class Property(JUnitBase):
    name = str
    value = str

    def __str__(self):
        return ''               # TODO

class Failure(JUnitBase):
    message = str
    type = str
    text = str

    def __str__(self):
        return ('<failure'
                ' type={self.type_attr}'
                ' message={self.message_attr}>'
                '{self.text}'
                '</failure>'.format(self=self.escaped_values()))

class SystemOut(JUnitBase):
    text = str

    def __str__(self):
        if self.text:
            return '<system-out>{self.text}</system-out>'.format(self=self.escaped_values())
        else:
            return ''

class Testcase(JUnitBase):
    classname = str
    name = str
    time = float
    system_out = SystemOut
    failure = Failure

    def print(self, file=sys.stdout):
        print(('<testcase'
               ' classname={self.classname_attr}'
               ' name={self.name_attr}'
               ' time="{self.time:.3f}">').format(self=self.escaped_values()),
               file = file)
        if self.failure:
            self.failure.print(file)
        if self.system_out:
            self.system_out.print(file)
        print("</testcase>", file=file)

class Testsuite(JUnitBase):
    errors = int
    failures = int
    hostname = str
    name = str
    tests = int
    time = float
    timestamp = datetime.datetime
    properties = list
    testcases = list
    system_out = SystemOut
    system_err = str

    def print(self, file = sys.stdout):
        ts = self.timestamp.replace(microsecond=0)
        print('<testsuite tests="{self.tests}" errors="{self.errors}" failures="{self.failures}" hostname={self.hostname_attr} name={self.name_attr} time="{self.time:.3f}" timestamp="{timestamp}">'.format(self=self.escaped_values(), timestamp=ts.isoformat()),
              file = file)
        print("<properties>", file=file)
        for p in self.properties:
            p.print(file=file)
        print("</properties>", file=file)
        for t in self.testcases:
            t.print(file=file)
        self.system_out.print(file=file)
        print("</testsuite>", file=file)

class Testsuites(JUnitBase):
    testsuites = list

    def print(self, file = sys.stdout):
        print('<?xml version="1.1" encoding="UTF-8" ?>', file=file)
        print('<testsuites>', file = file)
        for t in self.testsuites:
            t.print(file=file)
        print("</testsuites>", file=file)
