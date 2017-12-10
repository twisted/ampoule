#!/usr/bin/env python

# Before using me you need to startup an ampoule process that uses the
# mapreduce child, like this:
# twistd -no ampoule --child=mapreduce.MapReducer

from twisted.internet.protocol import ClientFactory
from twisted.python import filepath as fp
from twisted.internet import reactor, defer
from twisted.protocols import amp

from mapreduce import Map, Reduce
from ampoule.util import mainpoint

import collections

def mymap(in_, out):
    """
    I'm the mapping function executed in the pool.
    """
    aggregation = collections.defaultdict(lambda : 0)

    for line in in_.getContent().splitlines():
        for word in line.split():
            word.strip(",:;.'\"[]{}()*&^%$#@!`~><\\+=-_")
            aggregation[word] += 1

    f = out.open('wb')
    f.write("\n".join("%s %s" % word_frequency
                      for word_frequency in aggregation.items()))
    f.close()


def myreduce(files, out):
    """
    I'm the reducer function applied to a directory in the pool.
    """
    aggregation = collections.defaultdict(lambda : 0)
    for f in files:
        for line in f.getContent().splitlines():
            key, freq = line.split()
            aggregation[key] += int(freq)

    sorted_aggregation = sorted(aggregation.items(),
                                key=lambda t: t[1], reverse=True)
    f = out.open('ab')
    f.write("\n".join("%s %s" % word_frequency for word_frequency in sorted_aggregation))
    f.write('\n')
    f.close()

def map_step(pool, directory, resultdir):
    """
    I define how to walk in the directory that I was given and apply
    the mapper function, then whatever I return is passed to the
    successive steps as first argument.
    """
    outputdir = resultdir.child(directory.basename())
    outputdir.createDirectory()

    l = []
    for filename in directory.children():
        l.append(pool.callRemote(Map, mapper=mymap, filename=filename, outdir=outputdir))

    return defer.DeferredList(l).addCallback(lambda _: outputdir)

def reduce_step(outputdir, pool, resultdir):
    """
    I'm the reduce step and our reduce function assumes that the directory
    is fully processed and that there's a single reduce process per directory.
    """
    return pool.callRemote(Reduce, reducer=myreduce, directory=outputdir)









# Some boilerplate code that is useful to define how to use the
# functions above but nothing more than that.


class AMPFactory(ClientFactory):
    """
    I store variables useful for the protocol connected to the pool.
    """

    def __init__(self, dirs, resultdir, steps):
        self.dirs = dirs
        self.resultdir = resultdir
        self.steps = steps

class ClientAMP(amp.AMP):
    """
    The main orchestration logic in this process, how every function
    in this file is called and in which order and what they do.
    """
    @defer.inlineCallbacks
    def connectionMade(self):
        amp.AMP.connectionMade(self)
        resultdir = self.factory.resultdir
        steps = self.factory.steps
        l = []
        for directory in self.factory.dirs:
            d = steps[0](self, directory, resultdir)
            for step in steps[1:]:
                d = d.addCallback(step, self, resultdir)
            l.append(d)
        yield defer.DeferredList(l)
        reactor.stop()

def process(dirs, resultdir, steps):
    """
    setup twisted and run it with the known parameters.
    """
    c = AMPFactory(dirs, resultdir, steps)
    c.protocol = ClientAMP
    reactor.connectTCP("127.0.0.1", 8901, c)
    reactor.run()

@mainpoint
def main(args):
    """
    The mainpoint, the decorator makes this module resolvable by
    reflect.qual() used by our Function argument type. Here we
    define the steps of our processing and we execute them.
    """
    directory_names = [fp.FilePath(name) for name in args[2:]]
    results = fp.FilePath(args[1])
    results.remove()
    results.makedirs()
    steps = [map_step, reduce_step]
    process(directory_names, results, steps)

