import logging
import sys
from pythonjsonlogger import jsonlogger

from app.core.config import settings

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter to include more relevant fields.
    """
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if not log_record.get('timestamp'):
            log_record['timestamp'] = self.formatTime(record, self.datefmt)
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname
        log_record['logger_name'] = record.name
        log_record['line_no'] = record.lineno
        log_record['pathname'] = record.pathname
        log_record['process_id'] = record.process
        log_record['thread_id'] = record.thread

def configure_logging():
    """
    Configures the application-wide structured JSON logging.
    """
    log_level = settings.LOG_LEVEL.upper()
    numeric_level = getattr(logging, log_level, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    logger = logging.getLogger()
    logger.setLevel(numeric_level)

    # Clear existing handlers to prevent duplicate logs
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)

    # Configure stdout handler for JSON output
    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Set specific loggers to avoid excessive output from libraries
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.INFO)

    logger.info(f"Logging configured at level: {log_level}")