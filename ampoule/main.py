import os
import sys
import imp
import sets
import itertools

from twisted.internet import reactor, protocol, defer, error
from twisted.python import log, util, reflect
from twisted.protocols import amp

gen = itertools.count()

def startAMPProcess(conf):
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
    return startProcess(conf, extraArgs=conf.args)

def startProcess(conf, extraArgs=()):
    """
    @param prot: a L{protocol.ProcessProtocol} subclass
    @type prot: L{protocol.ProcessProtocol}
    
    @return: a tuple of the child process and the deferred finished.
             finished triggers when the subprocess dies for any reason.
    """
    prot = conf.connector
    spawnProcess(prot, conf.bootstrap,
                    extraArgs + conf.spawnArgs, packages=conf.packages,
                    **conf.kwargs)
    
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

def spawnProcess(processProtocol, bootstrap, args=(), env={},
                 path=None, uid=None, gid=None, usePTY=0,
                 packages=()):
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
