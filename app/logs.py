"""Where the investigation log goes: the server's terminal. See docs/decisions/0007."""
import logging

from app import config


def setup() -> None:
    app_log = logging.getLogger(name="app")
    app_log.setLevel(level=config.LOG_LEVEL)
    if not app_log.handlers:                 # --reload imports the app again
        handler = logging.StreamHandler()
        handler.setFormatter(fmt=logging.Formatter(fmt="%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
        app_log.addHandler(hdlr=handler)
    # httpx logs every request at INFO: the viewer and model calls are already
    # in our own lines, so its copy is only noise.
    logging.getLogger(name="httpx").setLevel(level=logging.WARNING)
