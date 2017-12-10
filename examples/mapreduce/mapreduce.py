from twisted.protocols import amp
from twisted.python import reflect
from twisted.internet import defer

from ampoule import child

class Function(amp.Argument):
    def toString(self, inObject):
        return reflect.qual(inObject)

    def fromString(self, inString):
        return reflect.namedAny(inString)


class Map(amp.Command):
    arguments = [('mapper', Function()),
                 ('filename', amp.Path()),
                 ('outdir', amp.Path())]

    response = [('result', amp.Path())]

class Reduce(amp.Command):
    arguments = [('reducer', Function()),
                 ('directory', amp.Path())]

    response = [('result', amp.Path())]

class MapReducer(child.AMPChild):
    def _call(self, fun, in_, out):
        return defer.maybeDeferred(fun, in_, out
            ).addCallback(lambda _: {'result': out})

    @Map.responder
    def map(self, mapper, filename, outdir):
        in_ = filename
        out = outdir.child(filename.basename()).siblingExtension('.map')
        return self._call(mapper, in_, out)

    @Reduce.responder
    def reduce(self, reducer, directory):
        in_ = directory.globChildren('*.map')
        out = directory.child('reduced.red')
        return self._call(reducer, in_, out)
