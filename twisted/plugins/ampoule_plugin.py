"""
Ampoule plugins for Twisted.
"""
import sys
from zope.interface import provider
from twisted.plugin import IPlugin
from twisted.python.usage import Options
from twisted.python import reflect
from twisted.application.service import IServiceMaker

@provider(IPlugin, IServiceMaker)
class AMPoulePlugin(object):
    """
    This plugin provides ways to create a process pool service in your
    system listening on a given port and interface and answering to a
    given set of commands.
    """

    tapname = "ampoule"
    description = "Run an AMPoule process pool"

    class options(Options):
        from twisted.application import reactors
        optParameters = [
            ["ampport", "p", 8901, "Listening port for the AMP service", int],
            ["ampinterface", "i", "0.0.0.0", "Listening interface for the AMP service"],
            ["child", "c", "ampoule.child.AMPChild", "Full module path to the children AMP class"],
            ["parent", "s", None, "Full module path to the parent process AMP class"],
            ["min", "l", 5, "Minimum number of processes in the pool", int],
            ["max", "u", 20, "Maximum number of processes in the pool", int],
            ["name", "n", None, "Optional process pool name"],
            ["max_idle", "d", 20, "Maximum number of idle seconds before killing a child", int],
            ["recycle", "r", 500, "Maximum number of calls before recycling a child", int],
            ["reactor", "R", "select", "Select the reactor for child processes"],
            ["timeout", "t", None, "Specify a timeout value for ProcessPool calls", int]
        ]

        def postOptions(self):
            """
            Check and finalize the value of the arguments.
            """
            self['child'] = reflect.namedAny(self['child'])
            if self['parent'] is not None:
                self['parent'] = reflect.namedAny(self['child'])
            if self['name']:
                self['name'] = self['name'].decode('utf-8')
        
        def opt_help_reactors(self):
            """Display a list of available reactors"""
            from twisted.application import reactors
            for r in reactors.getReactorTypes():
                sys.stdout.write('    %-4s\t%s\n' %
                                   (r.shortName, r.description))
            raise SystemExit(0)
    
    @classmethod
    def makeService(cls, options):
        """
        Create an L{IService} for the parameters and return it
        """
        from ampoule import service
        return service.makeService(options)
