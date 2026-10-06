import pytest

from backend.globals.models import OpenAIProvider, get_default_provider


def test_openai_provider_requires_its_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIProvider()


def test_openai_provider_accepts_an_explicit_key():
    provider = OpenAIProvider(api_key="sk-test")
    assert provider.api_key == "sk-test"
    assert provider.client.base_url.host == "api.openai.com"


def test_openai_provider_honors_a_custom_base_url():
    provider = OpenAIProvider(api_key="test-key", base_url="http://localhost:11434/v1")
    assert str(provider.client.base_url).startswith("http://localhost:11434/v1")


def test_get_default_provider_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    provider = get_default_provider()
    assert isinstance(provider, OpenAIProvider)
    assert provider.client.base_url.host == "api.openai.com"


def test_get_default_provider_cloudflare_requires_account_id(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "cloudflare")
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    with pytest.raises(ValueError, match="CLOUDFLARE_ACCOUNT_ID"):
        get_default_provider()


def test_get_default_provider_cloudflare_requires_its_api_token(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "cloudflare")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct-123")
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    with pytest.raises(ValueError, match="CLOUDFLARE_API_TOKEN"):
        get_default_provider()


def test_get_default_provider_cloudflare_builds_the_right_endpoint(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "cloudflare")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct-123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-token")
    provider = get_default_provider()
    assert isinstance(provider, OpenAIProvider)
    assert provider.api_key == "cf-token"
    assert "acct-123" in str(provider.client.base_url)
    assert "api.cloudflare.com" in str(provider.client.base_url)


def test_get_default_provider_ollama_defaults_to_localhost(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    provider = get_default_provider()
    assert str(provider.client.base_url).startswith("http://localhost:11434/v1")
    assert provider.api_key == "ollama"  # placeholder — Ollama doesn't check it


def test_get_default_provider_qwen_defaults_to_the_international_dashscope_endpoint(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "qwen")
    monkeypatch.setenv("QWEN_API_KEY", "qwen-key")
    monkeypatch.delenv("QWEN_REGION", raising=False)
    provider = get_default_provider()
    assert provider.api_key == "qwen-key"
    assert "dashscope-intl.aliyuncs.com" in str(provider.client.base_url)


def test_get_default_provider_qwen_cn_region_uses_the_mainland_endpoint(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "qwen")
    monkeypatch.setenv("QWEN_API_KEY", "qwen-key")
    monkeypatch.setenv("QWEN_REGION", "cn")
    provider = get_default_provider()
    assert "dashscope.aliyuncs.com" in str(provider.client.base_url)
    assert "intl" not in str(provider.client.base_url)


@pytest.mark.parametrize("alias", ["moonshot", "kimi"])
def test_get_default_provider_moonshot_accepts_both_name_aliases(monkeypatch, alias):
    monkeypatch.setenv("LLM_PROVIDER", alias)
    monkeypatch.setenv("MOONSHOT_API_KEY", "moonshot-key")
    monkeypatch.delenv("MOONSHOT_REGION", raising=False)
    provider = get_default_provider()
    assert provider.api_key == "moonshot-key"
    assert "api.moonshot.ai" in str(provider.client.base_url)


@pytest.mark.parametrize("alias", ["zhipu", "glm"])
def test_get_default_provider_zhipu_accepts_both_name_aliases(monkeypatch, alias):
    monkeypatch.setenv("LLM_PROVIDER", alias)
    monkeypatch.setenv("ZHIPU_API_KEY", "zhipu-key")
    monkeypatch.delenv("ZHIPU_REGION", raising=False)
    provider = get_default_provider()
    assert provider.api_key == "zhipu-key"
    assert "api.z.ai" in str(provider.client.base_url)


def test_get_default_provider_unknown_value_fails_loudly(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "made-up-provider")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_default_provider()
