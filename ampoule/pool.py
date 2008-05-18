import time
import random
choice = random.choice
now = time.time

from twisted.internet import defer, task
from twisted.python import log

from ampoule.main import startAMPProcess
from ampoule import commands

class ProcessPool(object):
    """
    This class generalizes the functionality of a pool of
    processes to which work can be dispatched.
    
    @ivar finished: Boolean flag, L{True} when the pool is finished.
    
    @ivar started: Boolean flag, L{True} when the pool is started.
    
    @ivar name: Optional name for the process pool
    
    @ivar min: Minimum number of subprocesses to set up
    
    @ivar max: Maximum number of subprocesses to set up
    
    @ivar max_idle: Maximum number of seconds of indleness in a child
    """

    finished = False
    started = False
    name = None

    processFactory = staticmethod(startAMPProcess)
    
    def __init__(self, ampChild=None, ampParent=None, min=5, max=20, name=None, max_idle=20):
        self.ampParent = ampParent
        self.ampChild = ampChild
        if ampChild is None:
            from ampoule.child import AMPChild
            self.ampChild = AMPChild
        self.min = min
        self.max = max
        self.name = name
        self.max_idle = max_idle
        
        self.processes = set()
        self.ready = set()
        self.busy = set()
        self._finishCallbacks = {}
        self._lastUsage = {}
        self.looping = task.LoopingCall(self._pruneProcesses)
        self.looping.start(max_idle, now=False)
    
    def start(self, ampChild=None):
        """
        Starts the ProcessPool with a given child protocol.
        
        @param ampChild: a L{ampoule.child.AMPChild} subclass.
        @type ampChild: L{ampoule.child.AMPChild} subclass
        """
        if ampChild is not None and not self.started:
            self.ampChild = ampChild
        self.finished = False
        self.started = True
        return self.adjustPoolSize()
    
    def _pruneProcesses(self):
        n = now()
        d = []
        for child, lastUse in self._lastUsage.iteritems():
            if len(self.processes) > self.min and (n - lastUse) > self.max_idle:
                # we are setting lastUse when processing finishes, it might be processing right now
                if child not in self.busy: 
                    # we need to remove this child from the ready set
                    # and the processes set because otherwise it might
                    # get calls from doWork
                    self.ready.discard(child)
                    self.processes.discard(child)
                    d.append(self.stopAWorker(child))
        return defer.DeferredList(d)
    
    def _pruneProcess(self, child):
        """
        Remove every trace of the process from this instance.
        """
        self.processes.discard(child)
        self.ready.discard(child)
        self.busy.discard(child)
        self._finishCallbacks.pop(child, None)
        self._lastUsage.pop(child, None)
    
    def _addProcess(self, child, finished):
        """
        Adds the newly created child process to the pool.
        """
        def restart(child, reason):
            log.msg("FATAL: Restarting after %s" % (reason,))
            self._pruneProcess(child)
            return self.startAWorker()

        def dieGently(data, child):
            log.msg("STOPPING: '%s'" % (data,))
            self._pruneProcess(child)
        
        self.processes.add(child)
        self.ready.add(child)
        finished.addCallback(dieGently, child
               ).addErrback(lambda reason: restart(child, reason))
        self._finishCallbacks[child] = finished
        self._lastUsage[child] = now()
    
    def startAWorker(self):
        ready, finished = self.processFactory(self.ampChild, ampParent=self.ampParent, packages=('twisted', 'ampoule'))
        return ready.addCallback(self._addProcess, finished)
    
    def doWork(self, command, **kwargs):
        """
        Sends the command to one child.
        
        @param command: an L{amp.Command} type object.
        @type command: L{amp.Command}
        
        @param kwargs: dictionary containing the arguments for the command.
        """
        def _returned(result, child):
            self.busy.discard(child)
            self.ready.add(child)
            self._lastUsage[child] = now()
            return result
        
        def _cb(child=None):
            if child is None:
                child = self.ready.pop()
            self.busy.add(child)
            return child.callRemote(command, **kwargs).addBoth(_returned, child)

        if self.ready: # there are unused processes, let's use them
            return _cb()
        else:
            if len(self.processes) < self.max:
                # no unused but we can start some new ones
                return self.startAWorker().addCallback(lambda _: _cb())
            else:
                # will have to go the random way, everyone is busy
                child = choice(list(self.processes))
                return _cb(child)
    
    def stopAWorker(self, child=None):
        if child is None:
            if self.ready:
                child = self.ready.pop()
            else:
                child = choice(list(self.processes))
        child.callRemote(commands.Shutdown)
        return self._finishCallbacks[child]
    
    @defer.inlineCallbacks
    def _startSomeWorkers(self):
        if len(self.processes) < self.max:
            yield self.startAWorker()

    @defer.inlineCallbacks
    def adjustPoolSize(self, min=None, max=None):
        
        if min is None:
            min = self.min
        if max is None:
            max = self.max

        assert min >= 0, 'minimum is negative'
        assert min <= max, 'minimum is greater than maximum'
        
        self.min = min
        self.max = max
        
        if self.started:
            while len(self.processes) > self.max:
                yield self.stopAWorker()
            while len(self.processes) < self.min:
                yield self.startAWorker()

    @defer.inlineCallbacks
    def stop(self):
        """
        Stops the process protocol.
        """
        self.finished = True
        for stopping in [self.stopAWorker(process) for process in self.processes]:
            yield stopping
        if self.looping.running:
            self.looping.stop()

    def dumpStats(self):
        log.msg('workers: %s' % len(self.processes))

pp = None

def deferToAMPProcess(command, **kwargs):
    """
    Helper function that sends a command to the default process pool
    and returns a deferred that fires when the result of the
    subprocess computation is ready.
    
    @param command: an L{amp.Command} subclass
    @param kwargs: dictionary containing the arguments for the command.
    
    @return: a L{defer.Deferred} with the data from the subprocess.
    """
    global pp
    if pp is None:
        pp = ProcessPool()
        return pp.start().addCallback(lambda _: pp.doWork(command, **kwargs))
    return pp.doWork(command, **kwargs)
