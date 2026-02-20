"""
HealthCheck: collects system and platform metrics for the /health endpoint.
"""
import time
from pathlib import Path
from typing import List

import psutil

from app.core.config import settings
from app.models.model_registry import model_registry
from app.schemas.response_schema import HealthResponse, ModelStatus

_START_TIME: float = time.time()


class HealthCheck:

    @staticmethod
    def _collect_model_statuses() -> List[ModelStatus]:
        statuses: List[ModelStatus] = []
        for operation, folder in settings.OPERATION_MODEL_MAP.items():
            model_path = settings.MODELS_DIR / folder
            statuses.append(
                ModelStatus(
                    name=f"{operation} ({folder})",
                    loaded=model_registry.is_loaded(folder),
                    path=str(model_path),
                )
            )
        return statuses

    @classmethod
    def get_health(cls) -> HealthResponse:
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        uptime = time.time() - _START_TIME

        model_statuses = cls._collect_model_statuses()
        all_loaded = all(m.loaded for m in model_statuses)
        status = "healthy" if all_loaded else "degraded"

        return HealthResponse(
            status=status,
            uptime_seconds=round(uptime, 2),
            memory_used_mb=round(mem.used / 1024 / 1024, 2),
            memory_total_mb=round(mem.total / 1024 / 1024, 2),
            cpu_percent=cpu,
            models=model_statuses,
        )
