"""评价 / 对话历史记录管理。

支持两类记录：
    - eval : 评价记录，由评价模块写入，preview 为评价摘要文本
    - chat : 对话记录，由聊天模块写入，包含完整对话消息列表
"""

import os
import json
import uuid
from datetime import datetime
from models.config import ASSETS_DIR


HISTORY_PATH = os.path.join(ASSETS_DIR, "history.json")
MAX_HISTORY = 200


def _load_history() -> list:
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except (json.JSONDecodeError, OSError):
        return []


def _save_history(records: list):
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(records[-MAX_HISTORY:], f, ensure_ascii=False, indent=2)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add_record(func_name: str, file_name: str, result_preview: str,
               full_content: str = "", messages: list = None,
               model: str = "") -> str:
    """添加评价类记录，返回记录 ID（兼容旧调用）。

    `messages` 是结构化的对话消息列表 [(role, content), ...]，传入后详情页可
    按"当前主题"动态重渲染气泡 / 文件卡片，避免归档时主题与查看时主题不一致
    导致的颜色错位（如白主题归档的记录在黑主题下看到白底气泡）。
    """
    records = _load_history()
    record_id = str(uuid.uuid4())[:8]
    records.append({
        "id": record_id,
        "type": "eval",
        "timestamp": _now(),
        "function": func_name,
        "file": file_name,
        "title": f"{func_name} - {file_name}" if file_name else func_name,
        "model": model,
        "messages": messages or [],
        "preview": (result_preview or "")[:200],
        "content": full_content or result_preview or "",
    })
    _save_history(records)
    return record_id


def add_chat_record(title: str, messages: list, content_html: str = "",
                    model: str = "") -> str:
    """添加对话类记录。

    messages: [(role, content), ...]
    """
    records = _load_history()
    record_id = str(uuid.uuid4())[:8]
    preview = ""
    for role, content in messages or []:
        if role == "user" and content:
            preview = content
            break
    if not title:
        title = preview[:30] or "对话"
    records.append({
        "id": record_id,
        "type": "chat",
        "timestamp": _now(),
        "title": title,
        "model": model,
        "messages": messages or [],
        "content_html": content_html,
        "preview": preview[:200],
    })
    _save_history(records)
    return record_id


def get_records(record_type: str = None) -> list:
    """获取记录（最新在前）。可按 type 过滤。"""
    records = _load_history()
    if record_type:
        records = [r for r in records if r.get("type", "eval") == record_type]
    return list(reversed(records))


def get_record_by_id(record_id: str) -> dict | None:
    """根据 ID 获取单条记录。"""
    records = _load_history()
    for r in records:
        if r.get("id") == record_id:
            return r
    return None


def update_record(record_id: str, **kwargs) -> bool:
    """更新记录字段。"""
    records = _load_history()
    for r in records:
        if r.get("id") == record_id:
            r.update(kwargs)
            _save_history(records)
            return True
    return False


def delete_record(record_id: str) -> bool:
    """删除记录。"""
    records = _load_history()
    new_records = [r for r in records if r.get("id") != record_id]
    if len(new_records) < len(records):
        _save_history(new_records)
        return True
    return False


def clear_all_records(record_type: str = None):
    """清空记录。指定 type 仅清空对应类型，否则清空全部。"""
    if record_type is None:
        _save_history([])
        return
    records = _load_history()
    records = [r for r in records if r.get("type", "eval") != record_type]
    _save_history(records)

