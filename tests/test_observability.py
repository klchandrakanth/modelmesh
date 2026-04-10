import logging
import json
import io
from modelmesh.observability.logging import configure_logging, get_logger


def test_get_logger_returns_logger():
    logger = get_logger("test.module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test.module"


def test_configure_logging_sets_level():
    configure_logging("WARNING")
    root = logging.getLogger()
    assert root.level == logging.WARNING
    # Reset
    configure_logging("INFO")
