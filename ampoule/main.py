import os
import sys
import imp
import sets
import itertools

from twisted.internet import reactor, protocol, defer, error
from twisted.python import log, util, reflect
from twisted.protocols import amp

gen = itertools.count()

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

def _checkRoundTrip(obj): 
    """
    Make sure that an object will properly round-trip through 'qual' and
    'namedAny'.

    Raise a L{RuntimeError} if they aren't.
    """
    tripped = reflect.namedAny(reflect.qual(obj))
    if tripped is not obj:
        raise RuntimeError("importing %r is not the same as %r" %
                           (reflect.qual(obj), obj))

def startAMPProcess(ampChild, *args, **kwargs):
    """
    @param ampChild: a L{ampoule.child.AMPChild} subclass.
    @type ampChild: L{ampoule.child.AMPChild}
    
    @param ampParent: an L{amp.AMP} subclass that implements the parent
                      protocol for this process pool
    @type ampParent: L{amp.AMP}
    
    @param args: a tuple of arguments that will be passed to the
                 subprocess
    @param kwargs: a dictionary that contains extra arguments for the
                   spawnProcess call.
    
    @param childReactor: a string that sets the reactor for child
                         processes
    @type childReactor: L{str}
    """
    _checkRoundTrip(ampChild)
    fullPath = reflect.qual(ampChild)
    ampParent = kwargs.pop('ampParent', None)
    if ampParent is None:
        ampParent = amp.AMP
    childReactor = kwargs.pop('childReactor', None)
    if childReactor is None:
        childReactor = "select"
    prot = AMPConnector(ampParent())
    return startProcess(prot, childReactor, fullPath, *args, **kwargs)

def startProcess(prot, *args, **kwargs):
    """
    @param prot: a L{protocol.ProcessProtocol} subclass
    @type prot: L{protocol.ProcessProtocol}
    
    @return: a tuple of the child process and the deferred finished.
             finished triggers when the subprocess dies for any reason.
    """
    spawnProcess(prot, tuple(args), **kwargs)
    
    # XXX: we could wait for startup here, but ... is there really any
    # reason to?  the pipe should be ready for writing.  The subprocess
    # might not start up properly, but then, a subprocess might shut down
    # at any point too. So we just return amp and have this piece to be
    # synchronous.
    return prot.amp, prot.finished

class AMPConnector(protocol.ProcessProtocol):
    """
    A L{ProcessProtocol} subclass that can understand and speak AMP.

    @ivar amp: the children AMP process
    @type amp: L{amp.AMP}
    
    @ivar finished: a deferred triggered when the process dies.
    @type finished: L{defer.Deferred}

    @ivar name: Unique name for the connector, much like a pid.
    @type name: int
    """

    def __init__(self, proto, name=None):
        """
        @param proto: An instance or subclass of L{amp.AMP}
        @type proto: L{amp.AMP}
        
        @param name: optional name of the subprocess.
        @type name: int
        """
        self.finished = defer.Deferred()
        self.amp = proto
        self.name = name
        if name is None:
            self.name = gen.next()

    def connectionMade(self):
        log.msg("Subprocess %s started." % (self.name,))
        self.amp.makeConnection(self)
        
    # Transport
    disconnecting = False

    def write(self, data):
        self.transport.writeToChild(3, data)

    def loseConnection(self):
        self.transport.closeChildFD(3)
        self.transport.closeChildfd(4)
        self.transport.loseConnection()

    def getPeer(self):
        return ('subprocess',)

    def getHost(self):
        return ('no host',)

    def childDataReceived(self, childFD, data):
        if childFD == 4:
            self.amp.dataReceived(data)
            return
        self.errReceived(data)

    def errReceived(self, data):
        for line in data.strip().splitlines():
            log.msg("FROM %s: %s" % (self.name, line))

    def processEnded(self, status):
        log.msg("Process: %s ended" % (self.name,))
        self.amp.connectionLost(status)
        if status.check(error.ProcessDone):
            self.finished.callback('')
            return
        self.finished.errback(status)

def spawnProcess(processProtocol, args=(), env={},
                 path=None, uid=None, gid=None, usePTY=0,
                 packages=(), bootstrap=BOOTSTRAP):
    env = env.copy()

    pythonpath = []
    for pkg in packages:
        p = os.path.split(imp.find_module(pkg)[1])[0]
        if p.startswith(os.path.join(sys.prefix, 'lib')):
            continue
        pythonpath.append(p)
    pythonpath = list(sets.Set(pythonpath))
    pythonpath.extend(env.get('PYTHONPATH', '').split(os.pathsep))
    env['PYTHONPATH'] = os.pathsep.join(pythonpath)
    args = (sys.executable, '-c', bootstrap) + args
    # childFDs variable is needed because sometimes child processes
    # misbehave and use stdout to output stuff that should really go
    # to stderr. Of course child process might even use the wrong FDs
    # that I'm using here, 3 and 4, so we are going to fix all these
    # issues when I add support for the configuration object that can
    # fix this stuff in a more configurable way.
    return reactor.spawnProcess(processProtocol, sys.executable, args,
                                env, path, uid, gid, usePTY,
                                childFDs={0:"w", 1:"r", 2:"r", 3:"w", 4:"r"})
