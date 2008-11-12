from twisted.protocols import amp
from twisted.python import reflect
from ampoule import child

class Configuration(object):
    ampChild = None
    ampParent = None
    childReactor = None
    bootstrap = None
    packages = None
    min = None
    max = None
    name = None
    maxIdle = None
    recycleAfter = None
    
    def extraSpawnProcessArgs(self):
        return {}

BOOTSTRAP = """\
import sys

def main(reactor, ampChildPath):
    from twisted.application import reactors
    reactors.installReactor(reactor)
    
    from twisted.python import log
    log.startLogging(sys.stderr)

    from twisted.internet import reactor, stdio
    from twisted.python import reflect

    ampChild = reflect.namedAny(ampChildPath)
    stdio.StandardIO(ampChild(), 3, 4)
    reactor.run()
main(sys.argv[1], sys.argv[2])
"""

class DefaultConfiguration(Configuration):
    ampChild = child.AMPChild
    ampParent = amp.AMP
    childReactor = "select"
    bootstrap = BOOTSTRAP
    _packages = set(["twisted", "ampoule"])
    min = 5
    max = 20
    name = None
    maxIdle = 20
    recycleAfter = 500
    _kwargs = {}
    _args = ()
    
    def addArg(self, arg):
        if isinstance(arg, dict):
            self._kwargs.update(arg)
        elif isinstance(arg, (list, tuple)):
            self._args = self._args + arg
        elif isinstance(arg, basestring):
            self._args = self._args + (arg,)
    
    def addPackage(self, package):
        self._packages.add(package)
    
    @property
    def packages(self):
        return tuple(self._packages)
    
    @property
    def args(self):
        self._checkRoundTrip(self.ampChild)
        return (self.childReactor, reflect.qual(self.ampChild))

    @property
    def spawnArgs(self):
        return self._args
    
    @property
    def kwargs(self):
        return self._kwargs
    
    @property
    def connector(self):
        from ampoule import main
        return main.AMPConnector(self.ampParent())

    def _checkRoundTrip(self, obj):
        """
        Make sure that an object will properly round-trip through 'qual' and
        'namedAny'.

        Raise a L{RuntimeError} if they aren't.
        """
        tripped = reflect.namedAny(reflect.qual(obj))
        if tripped is not obj:
            raise RuntimeError("importing %r is not the same as %r" %
                               (reflect.qual(obj), obj))
    
    def processFactory(self):
        from ampoule import main
        return main.startAMPProcess(self)
