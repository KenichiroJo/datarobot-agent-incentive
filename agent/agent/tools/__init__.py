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
"""コミッション計算ワークフロー用のツール群。

各モジュールは Pure Python で実装されており LLM を呼ばない。
LangGraph のノードから呼び出される / FastAPI 側から直接呼び出される
2 系統の利用パターンを想定している。
"""

from .anomaly_detector import detect_anomalies
from .commission_calculator import (
    build_master_key,
    calculate_commission,
)
from .excel_parser import (
    normalize_yyyymmdd,
    parse_master_excel,
    parse_sales_excel,
)
from .report_generator import generate_summary

__all__ = [
    "build_master_key",
    "calculate_commission",
    "detect_anomalies",
    "generate_summary",
    "normalize_yyyymmdd",
    "parse_master_excel",
    "parse_sales_excel",
]
