"""販売管理手数料計算エンジン。

このパッケージは LangGraph ノードから呼び出される Pure Python の計算ロジックを提供する。
LLM は使用せず、取引条件マスタを参照したルールベースの計算を行う。
"""

from app.commission_engine.anomaly_detector import detect_anomalies
from app.commission_engine.commission_calculator import calculate_commission
from app.commission_engine.excel_parser import parse_master_excel, parse_sales_excel
from app.commission_engine.report_generator import generate_summary
from app.commission_engine.schemas import (
    CommissionResult,
    MasterRecord,
    SalesRecord,
    SummaryReport,
)

__all__ = [
    "CommissionResult",
    "MasterRecord",
    "SalesRecord",
    "SummaryReport",
    "calculate_commission",
    "detect_anomalies",
    "generate_summary",
    "parse_master_excel",
    "parse_sales_excel",
]
