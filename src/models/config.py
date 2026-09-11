import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
PROMPT_DIR = os.path.join(ASSETS_DIR, "prompt")
CONFIG_PATH = os.path.join(ASSETS_DIR, "config.json")
API_KEY_PATH = os.path.join(ASSETS_DIR, "api_keys.json")


def load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            import commentjson
            return commentjson.load(f)
        except ImportError:
            return json.load(f)


def save_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def load_config() -> dict:
    return load_json(CONFIG_PATH)


def save_config(data: dict):
    save_json(CONFIG_PATH, data)


def load_api_keys() -> dict:
    return load_json(API_KEY_PATH)


def save_api_keys(data: dict):
    save_json(API_KEY_PATH, data)


def get_api_key(provider: str) -> str:
    """根据供应商名获取对应的 API key。"""
    keys = load_api_keys()
    key_map = {
        "deepseek": "deepseek_api_key",
        "openai": "OPENAI_API_KEY",
        "zhipu": "zhipu_api_key",
    }
    return keys.get(key_map.get(provider, provider), "")


def load_prompt(name: str, lang: str = "zh") -> str:
    """加载 prompt 模板。

    目录结构（按 UI 按钮的英文名分文件夹，与图1中的按钮标题一一对应）：
        assets/prompt/<button_dir>/<lang>.txt

    其中 ``button_dir`` 取按钮英文名小写下划线形式：
        paper_scoring / content_evaluation / ensemble_learning /
        retrieval_augmented_generation / reflexion / role_aware_reasoning /
        adversarial_criticism / innovation_comparison /
        comprehensive_evaluation

    `lang` 取 ``"zh"`` 或 ``"en"``；找不到对应语言文件时回退到中文。

    兼容旧调用（向后兼容三种历史写法）：
      - 老短 key (``"scoring"`` / ``"content"`` / ``"rag"`` / ``"role_aware"`` /
        ``"adversarial"`` / ``"decomposed"`` / ``"comprehensive"`` /
        ``"ensemble"``)；
      - 完整老文件名 (``"ReviewFormat_Scoring.txt"`` 等)；
      - 含路径片段的写法 (``"scoring/zh.txt"``)。
    所有这些都会通过 ``_to_short_key`` 归一到当前的长目录名。
    """
    short_key = _to_short_key(name)
    candidates = [
        os.path.join(PROMPT_DIR, short_key, f"{lang}.txt"),
        os.path.join(PROMPT_DIR, short_key, "zh.txt"),
        os.path.join(PROMPT_DIR, name),  # 极端兜底：原样当文件名
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    raise FileNotFoundError(
        f"Prompt 文件未找到 (name={name}, lang={lang}). "
        f"已尝试: {candidates}"
    )


# ── 名称归一化映射 ────────────────────────────────────────
# 把所有"老写法"统一转成当前 prompt 子目录名。
# 任何老短 key、老文件名、按钮 key 都通过这张表落到正确目录上，
# 这样模块代码、历史记录里硬编码的旧名字都不会失效。
_LEGACY_PROMPT_MAP = {
    # ── 老短 key → 新长目录 ──
    "scoring": "paper_scoring",
    "content": "content_evaluation",
    "ensemble": "ensemble_learning",
    "rag": "retrieval_augmented_generation",
    "role_aware": "role_aware_reasoning",
    "roleaware": "role_aware_reasoning",  # main_window 里有 "roleaware" 写法
    "adversarial": "adversarial_criticism",
    "decomposed": "innovation_comparison",
    "comprehensive": "comprehensive_evaluation",
    # reflexion 名字未变
    # ── 老文件名 → 新长目录 ──
    "ReviewFormat_Scoring.txt": "paper_scoring",
    "ReviewFormat_ContentEvaluation.txt": "content_evaluation",
    "ReviewFormat_Ensemble.txt": "ensemble_learning",
    "ReviewFormat_RAG.txt": "retrieval_augmented_generation",
    "ReviewFormat_Reflexion.txt": "reflexion",
    "ReviewFormat_RoleAware.txt": "role_aware_reasoning",
    "ReviewFormat_Adversarial.txt": "adversarial_criticism",
    "ReviewFormat_DecomposedSearch.txt": "innovation_comparison",
    "ReviewFormat_Comprehensive.txt": "comprehensive_evaluation",
}


def _to_short_key(name: str) -> str:
    """把任意 prompt 名归一化为当前 prompt 子目录名。

    支持以下输入：
      1. 当前长 key（``"paper_scoring"`` / ``"role_aware_reasoning"`` …）
         —— 原样返回
      2. 老短 key（``"scoring"`` / ``"role_aware"`` …）—— 走 LEGACY map
      3. 老文件名（``"ReviewFormat_Scoring.txt"`` 等）—— 走 LEGACY map
      4. 子路径（``"scoring/zh.txt"`` / ``"paper_scoring/en.txt"``）
         —— 取第一段后再归一一次
    """
    if not name:
        return ""
    if "/" in name or "\\" in name:
        first = name.replace("\\", "/").split("/", 1)[0]
        return _LEGACY_PROMPT_MAP.get(first, first)
    if name in _LEGACY_PROMPT_MAP:
        return _LEGACY_PROMPT_MAP[name]
    return name

