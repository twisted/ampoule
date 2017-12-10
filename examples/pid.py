from ampoule import child, util
from twisted.protocols import amp

class Pid(amp.Command):
    response = [("pid", amp.Integer())]

class MyChild(child.AMPChild):
    @Pid.responder
    def pid(self):
        import os
        return {"pid": os.getpid()}

@util.mainpoint
def main(args):
    import sys
    from twisted.internet import reactor, defer
    from twisted.python import log
    log.startLogging(sys.stdout)

    from ampoule import pool

    @defer.inlineCallbacks
    def _run():
        pp = pool.ProcessPool(MyChild, min=1, max=1)
        yield pp.start()
        result = yield pp.doWork(Pid)
        print("The Child process PID is:", result['pid'])
        yield pp.stop()
        reactor.stop()

    reactor.callLater(1, _run)
    reactor.run()
