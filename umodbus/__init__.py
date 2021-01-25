from logging import getLogger, MyHandler, INFO, DEBUG


log = getLogger('uModbus')
log.level = INFO
log.addHandler(MyHandler())

from .config import Config  # NOQA
conf = Config()
