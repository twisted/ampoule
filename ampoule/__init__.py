from .pool import deferToAMPProcess, pp
from .commands import Shutdown, Ping, Echo
from .child import AMPChild
from ._version import __version__ as _my_version

__version__ = _my_version.short()


__all__ = [
    'deferToAMPProcess',
    'pp',
    'Shutdown', 'Ping', 'Echo',
    'AMPChild',
    '__version__',
]
