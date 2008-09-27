import time
import random
import heapq
import itertools
choice = random.choice
now = time.time
count = itertools.count().next
pop = heapq.heappop

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
    
    @ivar maxIdle: Maximum number of seconds of indleness in a child
    
    @ivar recycleAfter: Maximum number of calls before restarting a subprocess,
                        0 to not recycle.
    """

    finished = False
    started = False
    name = None

    processFactory = staticmethod(startAMPProcess)
    
    def __init__(self, ampChild=None, ampParent=None, min=5, max=20, name=None, maxIdle=20, recycleAfter=30):
        self.ampParent = ampParent
        self.ampChild = ampChild
        if ampChild is None:
            from ampoule.child import AMPChild
            self.ampChild = AMPChild
        self.min = min
        self.max = max
        self.name = name
        self.maxIdle = maxIdle
        self.recycleAfter = recycleAfter
        self._queue = []
        
        self.processes = set()
        self.ready = set()
        self.busy = set()
        self._finishCallbacks = {}
        self._lastUsage = {}
        self._calls = {}
        self.looping = task.LoopingCall(self._pruneProcesses)
        self.looping.start(maxIdle, now=False)
    
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
        """
        Remove idle processes from the pool.
        """
        n = now()
        d = []
        for child, lastUse in self._lastUsage.iteritems():
            if len(self.processes) > self.min and (n - lastUse) > self.maxIdle:
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
        self._calls.pop(child, None)
    
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
        self._calls[child] = 0
        self._catchUp()
    
    def _catchUp(self):
        """
        If there are queued items in the list then run them.
        """
        if self._queue:
            _, (d, command, kwargs) = pop(self._queue)
            self._cb_doWork(command, _d=d, **kwargs)
    
    def startAWorker(self):
        """
        Start a worker and set it up in the system.
        """
        if self.finished:
            # this is a race condition: basically if we call self.stop()
            # while a process is being recycled what happens is that the
            # process will be created anyway. By putting a check for
            # self.finished here we make sure that in no way we are creating
            # processes when the pool is stopped.
            # The race condition comes from the fact that:
            # stopAWorker() is asynchronous while stop() is synchronous.
            # so if you call:
            # pp.stopAWorker(child).addCallback(lambda _: pp.startAWorker())
            # pp.stop()
            # You might end up with a dirty reactor due to the stop()
            # returning before the new process is created.
            return
        child, finished = self.processFactory(self.ampChild, ampParent=self.ampParent, packages=('twisted', 'ampoule'))
        return self._addProcess(child, finished)
    
    def _cb_doWork(self, command, _d=None, **kwargs):
        """
        Go and call the command.
        
        @param command: The L{amp.Command} to be executed in the child
        @type command: L{amp.Command}
        
        @param _d: The deferred for the calling code.
        @type _d: L{defer.Deferred}
        """
        def _returned(result, child, is_error=False):
            self.busy.discard(child)
            if not die:
                # we are not marked to be removed, so add us back to
                # the ready set and let's see if there's some catching
                # up to do
                self.ready.add(child)
                self._catchUp()
            else:
                # We should die and we do, then we start a new worker
                # to pick up stuff from the queue otherwise we end up
                # without workers and the queue will remain there.
                self.stopAWorker(child).addCallback(lambda _: self.startAWorker())
            self._lastUsage[child] = now()
            # we can't do recycling here because it's too late and
            # the process might have received tons of calls already
            # which would make it run more calls than what is
            # configured to do.
            if is_error:
                _d.errback(result)
                return _d
            else:
                _d.callback(result)
                return _d
        
        die = False
        child = self.ready.pop()
        self.busy.add(child)
        self._calls[child] += 1
        
        # Let's see if this call goes over the recycling barrier
        if self.recycleAfter and self._calls[child] >= self.recycleAfter:
            # it does so mark this child, using a closure, to be
            # removed at the end of the call.
            die = True
        return child.callRemote(command, **kwargs
            ).addCallback(_returned, child
            ).addErrback(_returned, child, is_error=True)

    
    def doWork(self, command, **kwargs):
        """
        Sends the command to one child.
        
        @param command: an L{amp.Command} type object.
        @type command: L{amp.Command}
        
        @param kwargs: dictionary containing the arguments for the command.
        """
        d = defer.Deferred()
        if self.ready: # there are unused processes, let's use them
            self._cb_doWork(command, _d=d, **kwargs)
            return d
        else:
            if len(self.processes) < self.max:
                # no unused but we can start some new ones
                # since startAWorker is synchronous we won't have a
                # race condition here in case of multiple calls to
                # doWork, so we will end up in the else clause in case
                # of such calls:
                # Process pool with min=1, max=1, recycle_after=1
                # [call(Command) for x in xrange(BIG_NUMBER)]
                self.startAWorker()
                self._cb_doWork(command, _d=d, **kwargs)
                return d
            else:
                # No one is free... just queue up and wait for a process
                # to start and pick up the first item in the queue.
                self._queue.append((count(), (d, command, kwargs)))
                return d
    
    def stopAWorker(self, child=None):
        """
        Gently stop a child so that it's not restarted anymore
        
        @param command: an L{ampoule.child.AmpChild} type object.
        @type command: L{ampoule.child.AmpChild} or None
        
        """
        if child is None:
            if self.ready:
                child = self.ready.pop()
            else:
                child = choice(list(self.processes))
        child.callRemote(commands.Shutdown)
        return self._finishCallbacks[child]
    
    def _startSomeWorkers(self):
        """
        Start a bunch of workers until we reach the max number of them.
        """
        if len(self.processes) < self.max:
            self.startAWorker()

    @defer.inlineCallbacks
    def adjustPoolSize(self, min=None, max=None):
        """
        Change the pool size to be at least min and less than max,
        useful when you change the values of max and min in the instance
        and you want the pool to adapt to them.
        """
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
                self.startAWorker()

    @defer.inlineCallbacks
    def stop(self):
        """
        Stops the process protocol.
        """
        self.finished = True
        l = [self.stopAWorker(process) for process in self.processes]
        d = defer.DeferredList(l)
        yield d
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
