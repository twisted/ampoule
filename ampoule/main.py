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

def main(ampChildPath):
    from twisted.python import log
    log.startLogging(sys.stderr)

    from twisted.internet import reactor, stdio
    from twisted.python import reflect

    ampChild = reflect.namedAny(ampChildPath)
    stdio.StandardIO(ampChild())
    reactor.run()
main(sys.argv[1])
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
    """
    _checkRoundTrip(ampChild)
    fullPath = reflect.qual(ampChild)
    ampParent = kwargs.pop('ampParent', None)
    if ampParent is None:
        ampParent = amp.AMP
    prot = AMPConnector(ampParent())
    return startProcess(prot, fullPath, *args, **kwargs)

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
        self.transport.write(data)

    def writeSequence(self, data):
        self.transport.writeSequence(data)

    def loseConnection(self):
        self.transport.loseConnection()

    def getPeer(self):
        return ('subprocess',)

    def getHost(self):
        return ('no host',)

    def outReceived(self, data):
        self.amp.dataReceived(data)

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
    return reactor.spawnProcess(processProtocol, sys.executable, args,
                                env, path, uid, gid, usePTY)
