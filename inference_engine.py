"""
InferenceEngine: wraps tokenizer + model and exposes a clean generate() API.
All prompt construction and decoding logic lives here.
"""
import asyncio
import time
from typing import Any, Optional

import torch

from app.core.config import settings
from app.core.logging import get_logger
from app.models.model_registry import LoadedModel

logger = get_logger(__name__)


class InferenceEngine:
    """
    Stateless inference abstraction.  Accepts a LoadedModel and a prompt,
    returns the generated text and a token count.
    """

    @staticmethod
    def _run_inference(
        loaded: LoadedModel,
        prompt: str,
        max_new_tokens: int,
        temperature: float,
        top_p: float,
    ) -> tuple[str, int]:
        """
        Synchronous (blocking) inference.  Must be called inside an executor
        so the asyncio event loop is never blocked.
        """
        tokenizer = loaded.tokenizer
        model = loaded.model
        device = loaded.device

        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        input_token_count = inputs["input_ids"].shape[1]

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=temperature > 0,
                pad_token_id=tokenizer.eos_token_id,
            )

        # Decode only the newly generated tokens.
        new_token_ids = output_ids[0][input_token_count:]
        generated_text = tokenizer.decode(new_token_ids, skip_special_tokens=True)
        output_token_count = len(new_token_ids)

        return generated_text.strip(), output_token_count

    @classmethod
    async def generate(
        cls,
        loaded: LoadedModel,
        prompt: str,
        max_new_tokens: int,
        temperature: float = settings.DEFAULT_TEMPERATURE,
        top_p: float = settings.DEFAULT_TOP_P,
    ) -> tuple[str, int]:
        """
        Async wrapper around blocking inference.

        Returns:
            Tuple of (generated_text, output_token_count).
        """
        loop = asyncio.get_event_loop()
        start = time.perf_counter()

        text, token_count = await loop.run_in_executor(
            None,
            cls._run_inference,
            loaded,
            prompt,
            max_new_tokens,
            temperature,
            top_p,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Inference complete | model=%s | tokens=%d | time=%.1fms",
            loaded.folder,
            token_count,
            elapsed_ms,
        )
        return text, token_count


# ── Prompt builders ───────────────────────────────────────────────────────────
# Centralised here so changing prompt templates doesn't require touching
# business logic in services.

def build_summarize_prompt(text: str, max_sentences: int, language: str) -> str:
    return (
        f"You are a professional summarization assistant.\n"
        f"Summarize the following text in exactly {max_sentences} concise sentence(s). "
        f"Write the summary in language code '{language}'. "
        f"Output only the summary text, nothing else.\n\n"
        f"TEXT:\n{text}\n\nSUMMARY:"
    )


def build_translate_prompt(text: str, source_lang: str, target_lang: str) -> str:
    return (
        f"You are a professional translation assistant.\n"
        f"Translate the following text from '{source_lang}' to '{target_lang}'. "
        f"Output only the translated text, nothing else.\n\n"
        f"TEXT:\n{text}\n\nTRANSLATION:"
    )


def build_classify_prompt(text: str, categories: list[str]) -> str:
    category_list = ", ".join(f'"{c}"' for c in categories)
    return (
        f"You are a text classification assistant.\n"
        f"Classify the following text into exactly one of these categories: {category_list}.\n"
        f"Respond with a JSON object only, in this exact format:\n"
        f'{{"label": "<chosen_category>", "confidence": <0.0-1.0>}}\n\n'
        f"TEXT:\n{text}\n\nCLASSIFICATION:"
    )
