"""手数料計算エージェントの State スキーマ。"""

from __future__ import annotations

from typing import Annotated, Literal, NotRequired, TypedDict

from langgraph.graph import MessagesState

ProcessingStatus = Literal[
    "idle",
    "parsing",
    "calculating",
    "review",
    "approved",
    "explained",
    "error",
]


class CommissionState(MessagesState):
    """6 ノードのワークフローで共有される State。

    MessagesState を継承するため messages: Annotated[list, add_messages] が含まれる。
    """

    # 入力
    uploaded_files: NotRequired[list[dict]]
    """[{"path": str, "filename": str, "detected_type": "sales"|"master"}]"""

    # data_parser ノードの出力
    sales_records: NotRequired[list[dict]]
    master_records: NotRequired[dict[str, dict]]

    # calculator ノードの出力
    calculation_results: NotRequired[list[dict]]
    pending_hitl: NotRequired[list[dict]]

    # hitl_review → approve の受け渡し
    user_decisions: NotRequired[list[dict]]
    approved_results: NotRequired[list[dict]]

    # サマリ
    summary: NotRequired[dict]

    # フロー制御
    processing_status: NotRequired[ProcessingStatus]
    error_message: NotRequired[str | None]
    next_route: NotRequired[str]
    """supervisor が選択した次ノード名 (data_parser / explainer / END)"""

    # 説明要求対象（explainer ノードで使う）
    explain_record_no: NotRequired[int | None]
