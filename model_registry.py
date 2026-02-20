"""
ModelRegistry: in-process store of loaded (tokenizer, model, device) triples.
Implements lazy loading – a model is loaded only on first use.
Thread-safety is achieved via asyncio.Lock (single-worker deployment).
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from app.core.config import settings
from app.core.logging import get_logger
from app.models.model_loader import ModelLoader

logger = get_logger(__name__)


@dataclass
class LoadedModel:
    folder: str
    tokenizer: Any
    model: Any
    device: str
    loaded_at: float = field(default_factory=time.time)


class ModelRegistry:
    """
    Singleton-style registry that manages loaded LLM instances.
    """

    def __init__(self) -> None:
        self._registry: Dict[str, LoadedModel] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, model_folder: str) -> asyncio.Lock:
        if model_folder not in self._locks:
            self._locks[model_folder] = asyncio.Lock()
        return self._locks[model_folder]

    async def get_or_load(self, model_folder: str) -> LoadedModel:
        """
        Return the LoadedModel for the given folder, loading it if necessary.
        Concurrent callers for the same model will queue on the lock.
        """
        if model_folder in self._registry:
            return self._registry[model_folder]

        async with self._get_lock(model_folder):
            # Double-checked locking.
            if model_folder in self._registry:
                return self._registry[model_folder]

            logger.info("Model '%s' not in registry – loading now.", model_folder)
            # Run blocking I/O in a thread pool so the event loop isn't blocked.
            loop = asyncio.get_event_loop()
            tokenizer, model, device = await loop.run_in_executor(
                None, ModelLoader.load, model_folder
            )
            loaded = LoadedModel(
                folder=model_folder,
                tokenizer=tokenizer,
                model=model,
                device=device,
            )
            self._registry[model_folder] = loaded
            logger.info("Model '%s' registered successfully.", model_folder)
            return loaded

    def is_loaded(self, model_folder: str) -> bool:
        return model_folder in self._registry

    def list_loaded(self) -> list[str]:
        return list(self._registry.keys())

    def unload(self, model_folder: str) -> bool:
        """Unload a model from memory. Returns True if it was loaded."""
        if model_folder not in self._registry:
            return False
        del self._registry[model_folder]
        logger.info("Model '%s' unloaded from registry.", model_folder)
        return True

    def all_model_folders(self) -> Dict[str, str]:
        """Return the full operation → folder mapping from config."""
        return dict(settings.OPERATION_MODEL_MAP)


# Application-level singleton.
model_registry = ModelRegistry()
