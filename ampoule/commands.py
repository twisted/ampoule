from twisted.protocols import amp

class Shutdown(amp.Command):
    responseType = amp.QuitBox

class Ping(amp.Command):
    response = [(b'response', amp.String())]

class Echo(amp.Command):
    arguments = [(b'data', amp.String())]
    response = [(b'response', amp.String())]
