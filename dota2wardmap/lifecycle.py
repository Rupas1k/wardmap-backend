import logging
import signal
import threading


def install_shutdown_handlers(logger: logging.Logger) -> threading.Event:
    shutdown = threading.Event()

    def request_shutdown(signum, _frame) -> None:
        logger.info("Received signal %s; shutting down", signal.Signals(signum).name)
        shutdown.set()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    return shutdown
