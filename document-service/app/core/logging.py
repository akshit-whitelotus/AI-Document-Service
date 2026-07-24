import logging
import sys
from app.middleware.correlation_id import correlation_id_ctx

class CorrelationIdFilter(logging.Filter):
    def filter(self, record:logging.LogRecord) -> bool:
        record.correlation_id=(
            correlation_id_ctx.get() or "N/A"
        )
        return True
def setup_logging() -> None:
    formatter=logging.Formatter(
        fmt=(
            "%(asctime)s "
            "%(levelname)s "
            "[%(correlation_id)s] "
            "%(name)s - "
            "%(message)s"
        )

    )
    handler=logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())
    root=logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    