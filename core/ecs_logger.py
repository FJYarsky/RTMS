# ==============================================================================
# RTMS — Real-Time Multicam System
# Formateador de logs estructurados JSON (Elastic Common Schema - ECS).
# Desarrollado por Joaquín Yarsky (joaquinyarsky@gmail.com)
# ==============================================================================

"""Formateador estructurado JSON compatible con ECS para observabilidad industrial."""

import datetime
import json
import logging
import os
from typing import Any, Dict

from core.__version__ import __version__


class ECSJsonFormatter(logging.Formatter):
    """Formatea registros de logging en JSON conforme al estándar Elastic Common Schema (ECS)."""

    def __init__(self, service_name: str = "rtms", version: str = __version__):
        super().__init__()
        self.service_name = service_name
        self.version = version

    def format(self, record: logging.LogRecord) -> str:
        # Timestamp ISO-8601 UTC
        now_dt = datetime.datetime.fromtimestamp(record.created, tz=datetime.timezone.utc)
        timestamp_str = now_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        ecs_doc: Dict[str, Any] = {
            "@timestamp": timestamp_str,
            "log.level": record.levelname,
            "message": record.getMessage(),
            "service.name": self.service_name,
            "service.version": self.version,
            "log.logger": record.name,
            "process.pid": os.getpid(),
            "process.thread.name": record.threadName,
        }

        if record.exc_info:
            ecs_doc["error.type"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            ecs_doc["error.message"] = str(record.exc_info[1])
            ecs_doc["error.stack_trace"] = self.formatException(record.exc_info)

        return json.dumps(ecs_doc, ensure_ascii=False)
