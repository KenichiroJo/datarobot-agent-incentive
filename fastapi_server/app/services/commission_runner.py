# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""LangGraph グラフのコンパイルと実行ラッパ。

設計判断 (plan §C):
- ``agent/`` ディレクトリを ``sys.path`` 局所拡張で取り込む（重量級依存の伝染を避ける）
- ``MyAgent`` 経由ではなく FastAPI プロセスで graph を所有して compile する
  - 理由: ``LangGraphAgent.invoke`` (datarobot_genai/langgraph/agent.py:83) は
    ``self.workflow.compile()`` を引数なしで呼ぶため HITL 対応不可
- process-wide で 1 個のコンパイル済みグラフを共有し、``thread_id == session_id`` で
  multi-tenant 分離
- LLM は ``get_llm()`` を使用 (AGENTS.md 準拠)
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------
# Cross-package import: agent/ ディレクトリを sys.path に追加
# ---------------------------------------------------------------
# このファイルの絶対パス: .../fastapi_server/app/services/commission_runner.py
# parents[3] = .../  (リポジトリルート)
_AGENT_DIR = Path(__file__).resolve().parents[3] / "agent"
if _AGENT_DIR.is_dir() and str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

logger = logging.getLogger(__name__)


# noqa: E402 -- sys.path 拡張後でないと agent.* を import できない
from agent.agent.commission_graph import commission_graph_factory  # noqa: E402

try:
    from datarobot_genai.langgraph.llm import get_llm  # noqa: E402

    _HAS_DR_GENAI = True
except ImportError:  # pragma: no cover
    _HAS_DR_GENAI = False
    logger.warning(
        "datarobot_genai が import できません。ChatOpenAI fallback を使用します。"
    )

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402


# ===============================================================
# LLM 初期化
# ===============================================================


def _build_llm():  # type: ignore[no-untyped-def]
    """LLM インスタンスを生成する。

    AGENTS.md 準拠で ``get_llm()`` を優先採用。datarobot_genai が無い、または
    呼び出し失敗時は ``ChatOpenAI`` 直接インスタンス化に fallback する
    (commission ワークフロー専有のため AGENTS.md 違反の影響は限定的)。
    """
    if _HAS_DR_GENAI:
        try:
            llm = get_llm(model_name=None)
            logger.info("LLM 初期化: datarobot_genai.get_llm() で構築完了")
            return llm
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_llm() 失敗のため ChatOpenAI fallback に切替: %s", exc)

    # Fallback: OPENAI_API_BASE + OPENAI_API_KEY を使った直接インスタンス化
    from langchain_openai import ChatOpenAI

    model_name = os.environ.get("LLM_MODEL_NAME", "azure-openai/gpt-4o")
    base_url = os.environ.get("OPENAI_API_BASE")
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get(
        "DATAROBOT_API_TOKEN", ""
    )
    if not base_url:
        raise RuntimeError(
            "LLM 初期化失敗: get_llm() が使えず、かつ OPENAI_API_BASE も未設定です。"
            ".env に OPENAI_API_BASE と OPENAI_API_KEY を設定してください。"
        )
    logger.info("LLM 初期化: ChatOpenAI fallback model=%s base=%s", model_name, base_url)
    return ChatOpenAI(model=model_name, base_url=base_url, api_key=api_key, streaming=True)


# ===============================================================
# Graph build
# ===============================================================


def build_compiled_commission_graph():  # type: ignore[no-untyped-def]
    """``MemorySaver`` + ``interrupt_before=['hitl_review']`` でコンパイルする。"""
    llm = _build_llm()
    workflow = commission_graph_factory(llm, tools=[], verbose=False)
    compiled = workflow.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["hitl_review"],
    )
    logger.info("commission graph compiled (interrupt_before=['hitl_review'])")
    return compiled


# ===============================================================
# SSE event helper
# ===============================================================


def sse_frame(event: dict[str, Any]) -> str:
    """SSE フレームの 1 メッセージを文字列で返す。

    ``data: {...}\\n\\n`` の形式。FastAPI 側で ``StreamingResponse`` の
    media_type='text/event-stream' で配信する。
    """
    import json as _json

    payload = _json.dumps(event, ensure_ascii=False, default=_default_json_encoder)
    return f"data: {payload}\n\n"


def _default_json_encoder(obj: Any) -> Any:
    """JSON エンコード時の Decimal / datetime 対応。"""
    from datetime import datetime, date
    from decimal import Decimal

    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return str(obj)
    return str(obj)
