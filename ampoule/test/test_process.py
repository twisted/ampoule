from cStringIO import StringIO as sio

from twisted.internet import error, defer
from twisted.python import failure, reflect
from twisted.trial import unittest
from twisted.protocols import amp
from ampoule import main, child, commands, pool

import good
import bad

good_path = reflect.fullFuncName(good.main)
bad_path = reflect.fullFuncName(bad.main)

class ShouldntHaveBeenCalled(Exception):
    pass

def _raise(_):
    raise ShouldntHaveBeenCalled(_)

class _FakeT(object):
    closeStdinCalled = False
    def __init__(self, s):
        self.s = s

    def closeStdin(self):
        self.closeStdinCalled = True

    def write(self, data):
        self.s.write(data)

class FakeAMP(object):
    connector = None
    reason = None
    def __init__(self, s):
        self.s = s
        
    def makeConnection(self, connector):
        if self.connector is not None:
            raise Exception("makeConnection called twice")
        self.connector = connector
    
    def connectionLost(self, reason):
        if self.reason is not None:
            raise Exception("connectionLost called twice")
        self.reason = reason
    
    def dataReceived(self, data):
        self.s.write(data)

class Ping(amp.Command):
    arguments = [('data', amp.String())]
    response = [('response', amp.String())]

class Pong(amp.Command):
    arguments = [('data', amp.String())]
    response = [('response', amp.String())]

class Child(child.AMPChild):
    def ping(self, data):
        return self.callRemote(Pong, data=data)
    Ping.responder(ping)

class First(amp.Command):
    arguments = [('data', amp.String())]
    response = [('response', amp.String())]

class Second(amp.Command):
    pass

class WaitingChild(child.AMPChild):
    deferred = None
    def first(self, data):
        self.deferred = defer.Deferred()
        return self.deferred.addCallback(lambda _: {'response': data})
    First.responder(first)
    def second(self):
        self.deferred.callback('')
        return {}
    Second.responder(second)

class Die(amp.Command):
    pass

class BadChild(child.AMPChild):
    def die(self):
        self.shutdown = False
        self.transport.loseConnection()
        return {}
    Die.responder(die)

class TestAMPConnector(unittest.TestCase):
    def _makeConnector(self, s, sa):
        a = FakeAMP(sa)
        ac = main.AMPConnector(a)
        assert ac.name is not None
        ac.transport = _FakeT(s)
        return ac
        
    def test_protocol(self):
        """
        Test that outReceived writes to AMP and that it triggers the
        finished deferred once the process ended.
        """
        s = sio()
        sa = sio()
        ac = self._makeConnector(s, sa)
        
        for x in xrange(99):
            ac.outReceived(str(x))
        
        ac.processEnded(failure.Failure(error.ProcessDone(0)))
        return ac.finished.addCallback(
            lambda _: self.assertEqual(sa.getvalue(), ''.join(str(x) for x in xrange(99)))
        )
        
    def test_protocol_failing(self):
        """
        Test that a failure in the process termination is correctly
        propagated to the finished deferred.
        """
        s = sio()
        sa = sio()
        ac = self._makeConnector(s, sa)
        
        ac.finished.addCallback(_raise)
        fail = failure.Failure(error.ProcessTerminated())
        self.assertFailure(ac.finished, error.ProcessTerminated)
        ac.processEnded(fail)

    def test_startProcess(self):
        """
        Test that startProcess actually starts a subprocess and that
        it receives data back from the process through AMP.
        """
        STRING = "ciao"
        wasReady = []
        def _readyCalled(child):
            wasReady.append(True)
        s = sio()
        a = FakeAMP(s)
        ready, finished = main.startProcess(main.AMPConnector(a), good_path, STRING, packages=("ampoule", "twisted"))
        def _eb(reason):
            print reason
        finished.addErrback(_eb)
        finished.addCallback(lambda _: self.assertEquals(s.getvalue(), STRING))
        ready.addCallback(_readyCalled)
        return finished.addCallback(lambda _: self.assertEquals(wasReady, [True]))
    
    def test_failing_deferToProcess(self):
        """
        Test failing subprocesses and the way they terminate and preserve
        failing information.
        """
        STRING = "ciao"
        s = sio()
        a = FakeAMP(s)
        ready, finished = main.startProcess(main.AMPConnector(a), bad_path, STRING, packages=("ampoule", "twisted"))
        self.assertFailure(finished, error.ProcessTerminated)
        finished.addErrback(lambda reason: self.assertEquals(reason.getMessage(), STRING))
        return finished

    def test_startAMPProcess(self):
        """
        Test that you can start an AMP subprocess and that it correctly
        accepts commands and correctly answers them.
        """
        STRING = "ciao"
        ready, finished = main.startAMPProcess(child.AMPChild, packages=('ampoule', 'twisted'))
        def _isReady(c):
            return c.callRemote(commands.Echo, data=STRING
                       ).addCallback(lambda response:
                            self.assertEquals(response['response'], STRING)
                       ).addCallback(lambda _: c.callRemote(commands.Shutdown))
        ready.addCallback(_isReady)
        return finished

    def test_startAMPAndParentProtocol(self):
        """
        Test that you can start an AMP subprocess and the children can
        call methods on their parent.
        """
        DATA = "CIAO"
        APPEND = "123"

        class Parent(amp.AMP):
            def pong(self, data):
                return {'response': DATA+APPEND}
            Pong.responder(pong)
        
        ready, finished = main.startAMPProcess(Child, ampParent=Parent, packages=('ampoule', 'twisted'))
        def _isReady(subp):
            return subp.callRemote(Ping, data=DATA
                       ).addCallback(lambda response:
                            self.assertEquals(response['response'], DATA+APPEND)
                       ).addCallback(lambda _: subp.callRemote(commands.Shutdown))
        ready.addCallback(_isReady)
        return finished

    def test_roundtripError(self):
        """
        Test that invoking a child using an unreachable class raises
        a L{RunTimeError} .
        """
        class Child(child.AMPChild):
            pass
        
        self.assertRaises(RuntimeError, main.startAMPProcess, Child, packages=('ampoule', 'twisted'))

class TestProcessPool(unittest.TestCase):
    def test_startStopWorker(self):
        """
        Test that starting and stopping a worker keeps the state of
        the process pool consistent.
        """
        pp = pool.ProcessPool()
        self.assertEquals(pp.started, False)
        self.assertEquals(pp.finished, False)
        self.assertEquals(pp.workers, 0)
        self.assertEquals(pp.processes, [])
        self.assertEquals(pp._finishCallbacks, {})
        
        def _checks(_):
            self.assertEquals(pp.started, False)
            self.assertEquals(pp.finished, False)
            self.assertEquals(pp.workers, 1)
            self.assertEquals(len(pp.processes), 1)
            self.assertEquals(len(pp._finishCallbacks), 1)
            return pp.stopAWorker()
        
        def _closingUp(_):
            self.assertEquals(pp.started, False)
            self.assertEquals(pp.finished, False)
            self.assertEquals(pp.workers, 0)
            self.assertEquals(len(pp.processes), 0)
            self.assertEquals(pp._finishCallbacks, {})
        return pp.startAWorker().addCallback(_checks).addCallback(_closingUp)

    def test_startAndStop(self):
        """
        Test that a process pool's start and stop method create the
        expected number of workers and keep state consistent in the
        process pool.
        """
        pp = pool.ProcessPool()
        self.assertEquals(pp.started, False)
        self.assertEquals(pp.finished, False)
        self.assertEquals(pp.workers, 0)
        self.assertEquals(pp.processes, [])
        self.assertEquals(pp._finishCallbacks, {})
        
        def _checks(_):
            self.assertEquals(pp.started, True)
            self.assertEquals(pp.finished, False)
            self.assertEquals(pp.workers, pp.min)
            self.assertEquals(len(pp.processes), pp.min)
            self.assertEquals(len(pp._finishCallbacks), pp.min)
            return pp.stop()
        
        def _closingUp(_):
            self.assertEquals(pp.started, True)
            self.assertEquals(pp.finished, True)
            self.assertEquals(pp.workers, 0)
            self.assertEquals(len(pp.processes), 0)
            self.assertEquals(pp._finishCallbacks, {})
        return pp.start().addCallback(_checks).addCallback(_closingUp)

    def test_adjustPoolSize(self):
        """
        Test that calls to pool.adjustPoolSize are correctly handled.
        """
        pp = pool.ProcessPool(min=10)
        self.assertEquals(pp.started, False)
        self.assertEquals(pp.finished, False)
        self.assertEquals(pp.workers, 0)
        self.assertEquals(pp.processes, [])
        self.assertEquals(pp._finishCallbacks, {})
        
        def _resize1(_):
            self.assertEquals(pp.started, True)
            self.assertEquals(pp.finished, False)
            self.assertEquals(pp.workers, pp.min)
            self.assertEquals(len(pp.processes), pp.min)
            self.assertEquals(len(pp._finishCallbacks), pp.min)
            return pp.adjustPoolSize(min=2, max=3)
        
        def _resize2(_):
            self.assertEquals(pp.started, True)
            self.assertEquals(pp.finished, False)
            self.assertEquals(pp.max, 3)
            self.assertEquals(pp.min, 2)
            self.assertEquals(pp.workers, pp.max)
            self.assertEquals(len(pp.processes), pp.max)
            self.assertEquals(len(pp._finishCallbacks), pp.max)
        
        def _resize3(_):
            return self.assertFailure(pp.adjustPoolSize(min=-1, max=5), AssertionError
                ).addCallback(lambda _:
                    self.assertFailure(pp.adjustPoolSize(min=5, max=1), AssertionError)
                ).addCallback(lambda _:
                    pp.stop()
                )
        
        return pp.start(
            ).addCallback(_resize1
            ).addCallback(_resize2
            ).addCallback(_resize3)

    def test_childRestart(self):
        """
        Test that a failing child process is immediately restarted.
        """
        pp = pool.ProcessPool(BadChild, min=1)
        STRING = "DATA"
        
        def _checks(_):
            d = pp._finishCallbacks.values()[0]
            pp.doWork(Die).addErrback(lambda _: None)
            return d.addBoth(_checksAgain)
        
        def _checksAgain(_):
            return pp.doWork(commands.Echo, data=STRING
                    ).addCallback(lambda result: self.assertEquals(result['response'], STRING))
        
        return pp.start(
            ).addCallback(_checks
            ).addBoth(lambda _: pp.stop())

    def test_parentProtocolChange(self):
        """
        Test that the father can use an AMP protocol too.
        """
        DATA = "CIAO"
        APPEND = "123"

        class Parent(amp.AMP):
            def pong(self, data):
                return {'response': DATA+APPEND}
            Pong.responder(pong)
        
        pp = pool.ProcessPool(Child, ampParent=Parent)
        def _checks(_):
            return pp.doWork(Ping, data=DATA
                       ).addCallback(lambda response:
                            self.assertEquals(response['response'], DATA+APPEND)
                       )

        return pp.start().addCallback(_checks).addBoth(lambda _: pp.stop())


    def test_deferToAMPProcess(self):
        """
        Test that deferToAMPProcess works as expected.
        """
        
        STRING = "CIAOOOO"
        def _call(_):
            return pool.deferToAMPProcess(commands.Echo, data=STRING
               ).addCallback(lambda result: self.assertEquals(result['response'], STRING))
        
        return pool.pp.start().addCallback(_call).addCallback(lambda _: pool.pp.stop())

    def test_checkStateInPool(self):
        """
        Test that busy and ready lists are correctly maintained.
        """
        pp = pool.ProcessPool(WaitingChild)
        
        DATA = "foobar"

        def _checks(_):
            d = pp.doWork(First, data=DATA)
            self.assertEquals(pp.started, True)
            self.assertEquals(pp.finished, False)
            self.assertEquals(pp.workers, pp.min)
            self.assertEquals(len(pp.processes), pp.min)
            self.assertEquals(len(pp._finishCallbacks), pp.min)
            self.assertEquals(len(pp.ready), pp.min-1)
            self.assertEquals(len(pp.busy), 1)
            child = pp.busy.pop()
            pp.busy.add(child)
            child.callRemote(Second)
            return d

        return pp.start(
            ).addCallback(_checks
            ).addBoth(lambda _: pp.stop())

    def test_growingToMax(self):
        """
        Test that the pool grows over time until it reaches max processes.
        """
        MAX = 5
        pp = pool.ProcessPool(WaitingChild, min=1, max=MAX)

        def _checks(_):
            self.assertEquals(pp.started, True)
            self.assertEquals(pp.finished, False)
            self.assertEquals(pp.workers, pp.min)
            self.assertEquals(len(pp.processes), pp.min)
            self.assertEquals(len(pp._finishCallbacks), pp.min)
            
            D = "DATA"
            d = [pp.doWork(First, data=D) for x in xrange(MAX)]

            self.assertEquals(pp.started, True)
            self.assertEquals(pp.finished, False)
            self.assertEquals(pp.workers, pp.max)
            self.assertEquals(len(pp.processes), pp.max)
            self.assertEquals(len(pp._finishCallbacks), pp.max)
            
            [child.callRemote(Second) for child in pp.processes]
            return defer.DeferredList(d)

        return pp.start(
            ).addCallback(_checks
            ).addBoth(lambda _: pp.stop())












