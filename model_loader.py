"""
ModelLoader: loads Hugging Face-compatible models from the local filesystem.
No internet access is used at any point.
"""
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import torch

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ModelLoader:
    """
    Responsible for loading tokenizer + model from a local directory.

    Supports any model compatible with the HuggingFace Transformers API
    (Qwen, DeepSeek, Mistral, LLaMA, etc.) as long as its weights
    reside in ./models/<model_folder_name>/.
    """

    @staticmethod
    def _resolve_model_path(model_folder: str) -> Path:
        model_path = settings.MODELS_DIR / model_folder
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model directory not found: {model_path}. "
                "Please place model weights in the correct folder before starting."
            )
        return model_path

    @staticmethod
    def _select_device() -> str:
        if torch.cuda.is_available():
            device = "cuda"
            logger.info("CUDA available – loading model on GPU.")
        else:
            device = "cpu"
            logger.info("CUDA not available – loading model on CPU.")
        return device

    @classmethod
    def load(cls, model_folder: str) -> Tuple[Any, Any, str]:
        """
        Load tokenizer and model from the local filesystem.

        Args:
            model_folder: Subfolder name inside settings.MODELS_DIR.

        Returns:
            Tuple of (tokenizer, model, device_string).

        Raises:
            FileNotFoundError: If model directory does not exist.
            RuntimeError:      If loading fails for any reason.
        """
        # Lazy import – only pay for torch/transformers when actually loading.
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "The 'transformers' package is not installed. "
                "Run: pip install transformers torch"
            ) from exc

        model_path = cls._resolve_model_path(model_folder)
        device = cls._select_device()

        logger.info("Loading tokenizer from: %s", model_path)
        tokenizer = AutoTokenizer.from_pretrained(
            str(model_path),
            local_files_only=True,
            trust_remote_code=True,
        )

        logger.info("Loading model from: %s (device=%s)", model_path, device)
        dtype = torch.float16 if device == "cuda" else torch.float32
        model = AutoModelForCausalLM.from_pretrained(
            str(model_path),
            local_files_only=True,
            trust_remote_code=True,
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
        )
        model.to(device)
        model.eval()

        logger.info("Model '%s' loaded successfully on %s.", model_folder, device)
        return tokenizer, model, device
