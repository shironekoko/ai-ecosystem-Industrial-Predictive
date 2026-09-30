import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("/logs") if Path("/logs").is_dir() else (Path(__file__).resolve().parents[2].parent / "logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)


class OTelLogFilter(logging.Filter):
    """Provides fallback values for otelTraceID and otelSpanID if OTel is not active"""
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "otelTraceID"):
            record.otelTraceID = "0"
        if not hasattr(record, "otelSpanID"):
            record.otelSpanID = "0"
        return True


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.addFilter(OTelLogFilter())
    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-8s] [%(name)s] [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] — %(message)s"
    )

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    fh = RotatingFileHandler(LOG_DIR / "app.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger
