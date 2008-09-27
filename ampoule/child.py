from twisted.python import log
from twisted.protocols import amp
from ampoule.commands import Echo, Shutdown, Ping

class AMPChild(amp.AMP):
    def __init__(self):
        super(AMPChild, self).__init__(self)
        self.shutdown = False

    def connectionLost(self, reason):
        amp.AMP.connectionLost(self, reason)
        from twisted.internet import reactor
        reactor.stop()
        if not self.shutdown:
            import os
            os._exit(-1)

    def shutdown(self):
        log.msg("Shutdown message received, goodbye.")
        self.shutdown = True
        return {}
    Shutdown.responder(shutdown)

    def ping(self):
        return {'response': "pong"}
    Ping.responder(ping)

    def echo(self, data):
        return {'response': data}
    Echo.responder(echo)
