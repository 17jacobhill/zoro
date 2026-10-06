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
    """Talks to any OpenAI-compatible chat-completions API, not only
    OpenAI itself — `base_url` is the whole mechanism. Used directly for
    OpenAI, and for Cloudflare Workers AI / Ollama via get_default_provider()
    below, since both expose an OpenAI-compatible /v1/chat/completions
    endpoint. A provider needing a genuinely different request/response
    shape (the documented-but-unimplemented qwen/zhipu options) would need
    its own LLMProvider subclass instead — this class only covers "same
    wire format, different base_url and key"."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        key_env_var: str = "OPENAI_API_KEY",
    ):
        self.api_key = api_key or os.getenv(key_env_var)
        if not self.api_key:
            raise ValueError(
                f"API key not found. Set {key_env_var} environment variable "
                "or pass api_key parameter."
            )
        timeout_seconds = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "90"))
        client_kwargs: Dict[str, Any] = {"api_key": self.api_key, "timeout": timeout_seconds}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)
        self.timeout_seconds = timeout_seconds
    
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
    """Previously ignored LLM_PROVIDER entirely and always returned
    OpenAIProvider() regardless of its value — .env.example documented
    ollama/qwen/zhipu as options, but none of them actually worked.
    openai/cloudflare/ollama are real now (all OpenAI-compatible wire
    format, just a different base_url/key). qwen/zhipu still have no
    provider implementation (they use different native SDKs, already
    present as dependencies but never wired to an LLMProvider subclass)
    — selecting them now fails loudly instead of silently running
    against OpenAI, which is strictly more correct even though it wasn't
    the thing asked for."""
    provider_type = os.getenv("LLM_PROVIDER", "openai").lower()

    if provider_type == "openai":
        return OpenAIProvider()

    if provider_type == "cloudflare":
        account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        if not account_id:
            raise ValueError(
                "LLM_PROVIDER=cloudflare requires CLOUDFLARE_ACCOUNT_ID to be set."
            )
        base_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"
        return OpenAIProvider(base_url=base_url, key_env_var="CLOUDFLARE_API_TOKEN")

    if provider_type == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        # Ollama doesn't check the key's value, but the OpenAI SDK requires
        # a non-empty string — OLLAMA_API_KEY is genuinely optional.
        api_key = os.getenv("OLLAMA_API_KEY") or "ollama"
        return OpenAIProvider(api_key=api_key, base_url=base_url)

    if provider_type in ("qwen", "zhipu"):
        raise ValueError(
            f"LLM_PROVIDER={provider_type} is documented in .env.example but has no "
            "provider implementation yet (it needs its own LLMProvider subclass using "
            "the native dashscope/zhipuai SDK, not the OpenAI-compatible client). "
            "Use openai, cloudflare, or ollama instead."
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {provider_type!r}. Use openai, cloudflare, or ollama.")
