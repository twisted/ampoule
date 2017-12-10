from ampoule import child, util

@util.mainpoint
def main(args):
    from twisted.internet import reactor, defer
    from ampoule import pool, Ping
    import time

    # enable logging to see what happens in children
    import sys
    from twisted.python import log
    log.startLogging(sys.stdout)

    @defer.inlineCallbacks
    def _run():
        pp = pool.ProcessPool(child.AMPChild, recycleAfter=5000)
        pp.min = 1
        pp.max = 5
        yield pp.start()
        t = time.time()
        REPEATS = 40000
        l = [pp.doWork(Ping) for x in range(REPEATS)]
        yield defer.DeferredList(l)
        print(REPEATS/(time.time() - t))
        yield pp.stop()
        reactor.stop()

    reactor.callLater(1, _run)
    reactor.run()
