from ampoule import child, util

class FooChild(child.AMPChild):
    pass

@util.mainpoint
def main(args):
    from twisted.internet import reactor, defer
    from ampoule import pool, Ping
    import time
    
    @defer.inlineCallbacks
    def _run():
        pp = pool.ProcessPool(FooChild, recycleAfter=10000)
        pp.min = 1
        pp.max = 5
        yield pp.start(FooChild)
        t = time.time()
        REPEATS = 40000
        l = [pp.doWork(Ping) for x in xrange(REPEATS)]
        yield defer.DeferredList(l)
        print REPEATS/(time.time() - t)
        yield pp.stop()
        reactor.stop()
    
    reactor.callLater(1, _run)
    reactor.run()
