import datetime
import types
import inspect
import sys

class JUnitBase:
    def __init__(self, **kwargs):
        """Initialize the object with kwargs as specified by class variables."""
        valid_members = [x for x in dir(self.__class__) if
                         not x.startswith('_') and
                         not inspect.isfunction(getattr(self.__class__, x))]
        for (key, val) in kwargs.items():
            if key in valid_members:
                if type(val) == getattr(self.__class__, key) or val == None:
                    v = val
                else:
                    v = getattr(self.__class__, key).__call__(val) # Construct the right type
                setattr(self, key, v)
            else:
                raise(Exception("'{key}' is not a valid member of '{cls}'".format(key=key, cls=self.__class__.__name__)))

        for key in valid_members:
            if key not in kwargs:
                setattr(self, key, getattr(self.__class__, key).__call__())

    def print(self, file=sys.stdout):
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
        return '<failure type="{self.type}" message="{self.message}">{self.text}</failure>'.format(self=self)

class Testcase(JUnitBase):
    classname = str
    name = str
    time = str
    failure = Failure

    def print(self, file=sys.stdout):
        print('<testcase classname="{self.classname}" name="{self.name}" time="{self.time}">'.format(self=self),
              file = file)
        if self.failure:
            self.failure.print(file)
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
    system_out = str
    system_err = str

    def print(self, file = sys.stdout):
        print('<?xml version="1.0" encoding="UTF-8" ?>', file=file)
        print('<testsuite tests="{self.tests}" errors="{self.errors}" failures="{self.failures}" hostname="{self.hostname}" name="{self.name}" time="{self.time}" timestamp="{self.timestamp}"'.format(self=self),\
              file = file)
        print("<properties>", file=file)
        for p in self.properties:
            p.print(file=file)
        print("</properties>", file=file)
        for t in self.testcases:
            t.print(file=file)
        print("<system-out></system-out>\n<system-err></system-err>\n</testsuite>", file=file)
