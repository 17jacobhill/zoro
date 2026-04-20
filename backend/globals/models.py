import os
from typing import Optional, Dict, Any, List

import logging
import traceback

from openai import OpenAI
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

class LLMProvider:
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        
        raise NotImplementedError

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        self.client = OpenAI(api_key=self.api_key)
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-5",
        temperature: Optional[float] = None,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        logger = logging.getLogger(__name__)

        completion_kwargs = {
            "model": model,
            "messages": messages,
            **kwargs
        }

        # GPT-5 requires max_completion_tokens; callers must provide correct params.
        
        # Only add temperature if specified and not using GPT-5
        if temperature is not None and not model.startswith("gpt-5"):
            completion_kwargs["temperature"] = temperature
        
        if response_format:
            completion_kwargs["response_format"] = response_format

        try:
            msg_lens = [len((m.get("content") or "")) for m in (messages or [])]
            logger.info(
                "OpenAIProvider.chat_completion call model=%s keys=%s max_tokens=%s max_completion_tokens=%s msg_count=%s msg_lens=%s\nstack=%s",
                model,
                sorted(list(completion_kwargs.keys())),
                completion_kwargs.get("max_tokens"),
                completion_kwargs.get("max_completion_tokens"),
                len(messages or []),
                msg_lens,
                "".join(traceback.format_stack(limit=12)),
            )
        except Exception:
            logger.exception("OpenAIProvider.chat_completion logging failed")
        
        response = self.client.chat.completions.create(**completion_kwargs)
        return response.choices[0].message.content

def get_default_provider() -> LLMProvider:
    provider_type = os.getenv("LLM_PROVIDER", "openai").lower()

    return OpenAIProvider()
