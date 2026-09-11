"""统一的 LLM 调度层。

提供两个核心能力：

1. **主审模型**（summary / single-turn）—— 由用户在主页右下角下拉里选定的
   `provider/model` 决定。所有评价模块（scoring / content / rag / decomposed /
   ensemble 的汇总 / adversarial 的最终融合）都走这个角色，保证"用户选了谁，
   评价就由谁主导"。

2. **并行评价池**（parallel pool）—— 固定取自 `SiliconFlow` 中已 verified 的
   全部模型；这是聚合多家厂商模型的天然平台。集成评价（ensemble）和对抗式
   评价（adversarial 的 attack/defense 视角）都从这个池子取若干模型，达成
   "多模型对抗 / 多模型聚合"的效果。

退化策略：当 SiliconFlow 未配置时，退回到使用主审 provider 自己的模型列表
作为并行池（参见 `resolve_parallel_pool`）。
"""

import re
from typing import List, Tuple, Iterable, Optional


_THINK_TAGS = r"(?:think|thinking|reasoning|thought)"
_RE_THINK_COMPLETE = re.compile(
    rf"<\|?{_THINK_TAGS}\|?>.*?<\|?/{_THINK_TAGS}\|?>\s*",
    re.DOTALL,
)
_RE_THINK_OPEN = re.compile(
    rf"<\|?{_THINK_TAGS}\|?>(?:(?!<\|?/{_THINK_TAGS}\|?>).)*$",
    re.DOTALL,
)


def _strip_think(text: str) -> str:
    """移除模型输出中的思考过程。

    覆盖多种标签格式：
    - <think>...</think>
    - <|thinking|>...</|thinking|>
    - <reasoning>...</reasoning>
    """
    text = _RE_THINK_COMPLETE.sub("", text)
    text = _RE_THINK_OPEN.sub("", text)
    return text

from models.config import load_config, load_api_keys


# ─────────────────────────────────────────────────────
#  Anthropic → OpenAI 适配器
# ─────────────────────────────────────────────────────
class _AnthropicOpenAIAdapter:
    """让 Anthropic SDK 对外暴露与 OpenAI SDK 一致的 .chat.completions.create() 接口。"""

    _DEFAULT_BASE = "https://api.anthropic.com"

    def __init__(self, api_key: str, base_url: str = "", timeout: float = 300):
        from anthropic import Anthropic
        kwargs = {"api_key": api_key, "timeout": timeout}
        if base_url and base_url.rstrip("/") != self._DEFAULT_BASE:
            kwargs["base_url"] = base_url.rstrip("/")
        self._client = Anthropic(**kwargs)
        self.chat = self

    @property
    def completions(self):
        return self

    def create(self, *, model, messages, temperature=0.7,
               max_tokens=4096, stream=False, **_kw):
        system_text = ""
        user_msgs = []
        for m in messages:
            if m["role"] == "system":
                system_text += m["content"] + "\n"
            else:
                user_msgs.append({"role": m["role"], "content": m["content"]})
        if not user_msgs:
            user_msgs = [{"role": "user", "content": ""}]

        kwargs = dict(
            model=model, messages=user_msgs,
            max_tokens=max_tokens, temperature=temperature,
        )
        if system_text.strip():
            kwargs["system"] = system_text.strip()

        if stream:
            return self._stream(kwargs)
        resp = self._client.messages.create(**kwargs)
        text = ""
        for block in resp.content:
            if hasattr(block, "text"):
                text += block.text
        return _FakeCompletionResponse(text)

    def _stream(self, kwargs):
        with self._client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield _FakeStreamChunk(text)


class _FakeCompletionResponse:
    def __init__(self, text: str):
        self.choices = [_FakeChoice(text)]


class _FakeChoice:
    def __init__(self, text: str):
        self.message = _FakeMessage(text)
        self.delta = _FakeDelta(text)


class _FakeMessage:
    def __init__(self, text: str):
        self.content = text


class _FakeDelta:
    def __init__(self, text: str):
        self.content = text


class _FakeStreamChunk:
    def __init__(self, text: str):
        self.choices = [_FakeChoice(text)]


# 并行池的硬上限（取自 SiliconFlow 的所有 verified 模型时不超过这个数）
HARD_MAX_PARALLEL_MODELS = 8
# 退化路径下，从「主模型所在供应商」最多取多少模型作为并行池
FALLBACK_MAX_PARALLEL_MODELS = 3


# ─────────────────────────────────────────────────────
#  Provider → API Key 字段映射（与 settings_view.LLM_PROVIDERS 对齐）
# ─────────────────────────────────────────────────────
def provider_key_field(provider_key: str) -> str:
    mapping = {
        "deepseek": "deepseek_api_key",
        "siliconflow": "siliconflow_api_key",
        "qwen": "qwen_api_key",
        "openai": "OPENAI_API_KEY",
        "azure": "azure_openai_api_key",
        "anthropic": "anthropic_api_key",
        "gemini": "gemini_api_key",
        "zhipu": "zhipu_api_key",
        "custom": "custom_api_key",
    }
    return mapping.get(provider_key, f"{provider_key}_api_key")


# ─────────────────────────────────────────────────────
#  统一构造 OpenAI 兼容 client
# ─────────────────────────────────────────────────────
def build_openai_client(provider_key: str, provider_cfg: dict):
    """统一构造一个 OpenAI 兼容客户端。

    任一供应商的 base_url 缺失或 API Key 未配置 / 仍是 ``YOUR_*`` 占位符时，
    抛出 ``RuntimeError``，让调用方决定如何降级或提示用户。

    超时策略：
      - 默认 read=300s（应对 Qwen-235B / GLM-4.5 等大模型 + 多轮思维链
        + SiliconFlow 这种聚合平台首次冷启动较慢的场景）；
      - connect 仍保持 15s，连接立即失败的话不必等 5 分钟才报错；
      - 流式调用时 read 计时器在每个 chunk 到达后会被重置，所以 300s
        其实是"两个 chunk 之间的最大空窗"，几乎不会触发。
    """
    import httpx
    from openai import OpenAI

    api_key = (load_api_keys() or {}).get(provider_key_field(provider_key), "")
    if not api_key or api_key.startswith("YOUR_"):
        raise RuntimeError(
            f"API Key for provider '{provider_key}' is not configured. "
            f"Please set it in Settings \u2192 LLM Settings \u2192 {provider_key}."
        )

    base_url = (provider_cfg.get("base_url") or "").rstrip("/")
    if not base_url:
        raise RuntimeError(f"Base URL for provider '{provider_key}' is empty.")

    read_timeout = provider_cfg.get("timeout", 300)
    timeout = httpx.Timeout(connect=15.0, read=read_timeout, write=30.0, pool=10.0)

    # ── Azure OpenAI：使用专用 AzureOpenAI 客户端 ──
    if provider_key == "azure":
        from openai import AzureOpenAI
        api_version = provider_cfg.get("api_version", "2024-10-21")
        return AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=base_url,
            http_client=httpx.Client(timeout=timeout),
        )

    # ── Anthropic：原生 API 不兼容 OpenAI 格式，需要 anthropic SDK ──
    if provider_key == "anthropic":
        try:
            from anthropic import Anthropic
            return _AnthropicOpenAIAdapter(
                api_key=api_key,
                base_url=base_url,
                timeout=read_timeout,
            )
        except ImportError:
            raise RuntimeError(
                "Anthropic provider requires the 'anthropic' package.\n"
                "Run: pip install anthropic"
            )

    # ── Gemini：追加 /openai 使用 Google 的 OpenAI 兼容端点 ──
    if provider_key == "gemini":
        if "/openai" not in base_url:
            base_url += "/openai"
        return OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=httpx.Client(timeout=timeout),
        )

    # ── 通用 OpenAI 兼容供应商 ──
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        http_client=httpx.Client(timeout=timeout),
    )


# ─────────────────────────────────────────────────────
#  角色解析
# ─────────────────────────────────────────────────────
def resolve_summary_role(selected_model: str) -> Tuple[str, str, dict]:
    """解析「主审 / 汇总」角色。

    返回 (provider, model, provider_cfg)。

    选取规则：
      1. 解析 ``selected_model`` (`"provider/model"`) 取主审；
      2. 若用户没选，或选定的供应商不在配置里，则退回到第一个 ``verified`` 的供应商。
    """
    cfg = load_config()
    providers_cfg = cfg.get("llm_providers", {}) or {}

    provider, model = "", ""
    if selected_model and "/" in selected_model:
        provider, model = selected_model.split("/", 1)

    if not provider or provider not in providers_cfg:
        for k, pcfg in providers_cfg.items():
            if pcfg.get("verified"):
                provider = k
                ms = pcfg.get("models") or []
                model = ms[0] if ms else ""
                break

    return provider, model, providers_cfg.get(provider, {}) or {}


def resolve_parallel_pool(
    selected_model: str = "",
    max_models: int = HARD_MAX_PARALLEL_MODELS,
) -> Tuple[str, List[str], dict, bool]:
    """解析「并行池」角色。

    返回 (provider, models, provider_cfg, from_siliconflow)。

    主路径：取 SiliconFlow 中所有已 verified 模型（最多 ``max_models`` 个）。
    退化路径：当 SiliconFlow 未配置时，使用主审 provider 自己的模型列表，
    最多 ``FALLBACK_MAX_PARALLEL_MODELS`` 个。
    """
    cfg = load_config()
    providers_cfg = cfg.get("llm_providers", {}) or {}

    sf_cfg = providers_cfg.get("siliconflow", {}) or {}
    sf_models = list(sf_cfg.get("models") or []) if sf_cfg.get("verified") else []
    if sf_models:
        return "siliconflow", sf_models[:max_models], sf_cfg, True

    summary_provider, summary_model, summary_cfg = resolve_summary_role(selected_model)
    all_models = list(summary_cfg.get("models") or [])
    ordered: List[str] = []
    if summary_model and summary_model in all_models:
        ordered.append(summary_model)
    for m in all_models:
        if m not in ordered:
            ordered.append(m)
        if len(ordered) >= FALLBACK_MAX_PARALLEL_MODELS:
            break
    if not ordered and summary_model:
        ordered = [summary_model]
    return summary_provider, ordered, summary_cfg, False


# ─────────────────────────────────────────────────────
#  主审模型 - 流式 / 非流式调用
# ─────────────────────────────────────────────────────
def _resolve_and_build(selected_model: str = "",
                       temperature: Optional[float] = None,
                       max_tokens: Optional[int] = None):
    """公共辅助：解析 provider/model，构建 client，读取用户参数。"""
    provider, model, pcfg = resolve_summary_role(selected_model)
    if not provider or not model:
        raise RuntimeError(
            "No usable LLM provider/model configured. "
            "Please configure at least one provider in Settings and pick a model on the home page."
        )
    client = build_openai_client(provider, pcfg)
    temp = temperature if temperature is not None else (pcfg.get("temperature", 70) / 100.0)
    mt = max_tokens if max_tokens is not None else pcfg.get("max_tokens", 4096)
    use_stream = pcfg.get("streaming", True)
    return client, model, temp, mt, use_stream


def chat_stream(
    messages: list,
    selected_model: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Iterable[str]:
    """以"主页选定模型"作为主审，发起一次流式 chat completion。

    每次 yield 累计的全文（与既有 `_ChatWorker` 等期望的格式一致）。
    若用户在设置中关闭了 Streaming，自动降级为非流式调用，完成后一次性 yield 全文。
    """
    client, model, temp, mt, use_stream = _resolve_and_build(
        selected_model, temperature, max_tokens)

    if not use_stream:
        resp = client.chat.completions.create(
            model=model, messages=messages,
            temperature=temp, max_tokens=mt, stream=False,
        )
        raw = resp.choices[0].message.content or ""
        cleaned = _strip_think(raw)
        if cleaned:
            yield cleaned
        return

    resp = client.chat.completions.create(
        model=model, messages=messages,
        temperature=temp, max_tokens=mt, stream=True,
    )
    full = ""
    for chunk in resp:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        piece = getattr(delta, "content", None)
        if piece:
            full += piece
            cleaned = _strip_think(full)
            if cleaned:
                yield cleaned


def chat_nonstream(
    messages: list,
    selected_model: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """以"主页选定模型"作为主审，发起一次非流式 chat completion。"""
    client, model, temp, mt, _ = _resolve_and_build(
        selected_model, temperature, max_tokens)

    resp = client.chat.completions.create(
        model=model, messages=messages,
        temperature=temp, max_tokens=mt, stream=False,
    )
    raw = resp.choices[0].message.content or ""
    return _strip_think(raw)


def call_specific_model_nonstream(
    provider: str, provider_cfg: dict, model: str,
    messages: list,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    json_mode: bool = False,
) -> str:
    """指定 provider/model 做一次非流式调用。供并行池场景使用。

    `json_mode=True` 时尝试启用 OpenAI 兼容的 `response_format=json_object`，
    强约束模型只输出 JSON。若该 provider 不支持，会自动降级为普通调用，
    上层仍需用容错解析器处理输出。
    """
    client = build_openai_client(provider, provider_cfg)
    temp = temperature if temperature is not None else (provider_cfg.get("temperature", 70) / 100.0)
    mt = max_tokens if max_tokens is not None else provider_cfg.get("max_tokens", 4096)

    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temp,
        max_tokens=mt,
        stream=False,
    )
    if json_mode:
        try:
            resp = client.chat.completions.create(
                response_format={"type": "json_object"}, **kwargs,
            )
            return _strip_think(resp.choices[0].message.content or "")
        except Exception:
            pass
    resp = client.chat.completions.create(**kwargs)
    return _strip_think(resp.choices[0].message.content or "")

