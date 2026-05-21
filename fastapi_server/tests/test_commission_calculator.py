"""commission_calculator の単体テスト。"""

from __future__ import annotations

from datetime import datetime

from app.commission_engine.anomaly_detector import detect_anomalies
from app.commission_engine.commission_calculator import calculate_commission
from app.commission_engine.excel_parser import make_lookup_key
from app.commission_engine.report_generator import generate_summary


def _master_entry(**overrides) -> dict:
    base = {
        "key": "201903013620260301ずっとPREMIUMプランクレジットカード",
        "partner_name": "株式会社フォーカスタマーズ",
        "primary_partner_code": 2019030136,
        "commission_kbn": "Shot",
        "condition_definition": "獲得ベース",
        "payment_definition": "出荷ベース",
        "product": "ずっとPREMIUMプラン",
        "payment_method": "クレジットカード",
        "basic_commission": 41000.0,
        "volume_incentive": 0.0,
        "special_commission_1": 0.0,
        "special_commission_2": 0.0,
        "qi_scope": 0.0,
        "qi_split_period": 0.0,
        "debit_initial_fee": 0.0,
        "referral_kbn": 0.0,
        "referral_commission": 0.0,
        "continuous_flag_25_37": 0.0,
        "continuous_commission": 0.0,
        "pap_kbn": None,
        "pap_commission": 0.0,
        "pas_kbn": "Stock",
        "pas_commission": 250.0,
        "ph_kbn": "Shot",
        "ph_commission": 2500.0,
        "return_condition": "本数",
        "return_full_condition": "12本未満",
        "return_half_condition": "24本未満",
        "penalty": 0.0,
    }
    base.update(overrides)
    return base


def _sales_record(**overrides) -> dict:
    base = {
        "record_no": 1001,
        "ファイル区分": "販売店_サーバー初回",
        "contract_id": 9999,
        "application_date": datetime(2026, 3, 19),
        "application_month": datetime(2026, 3, 1),
        "product_category": "サーバー",
        "product_name": "ずっとPREMIUMプラン",
        "payment_method_raw": "クレジット(GMO)",
        "payment_method": "クレジットカード",
        "partner_code": 2019030136,
        "delivery_count": 1,
        "customer_price": 0,
        "lookup_key": "201903013620260301ずっとPREMIUMプランクレジットカード",
    }
    base.update(overrides)
    return base


def test_master_hit_basic_calculation() -> None:
    """マスタヒット時の基本コミッション計算。"""
    master = {_master_entry()["key"]: _master_entry()}
    result = calculate_commission(_sales_record(), master)

    assert result["master_found"] is True
    assert result["basic_commission"] == 41000
    assert result["pas_commission"] == 250
    assert result["ph_commission"] == 2500
    assert result["return_amount"] == 0  # 初回のため戻入なし
    assert result["total_commission"] == 43750
    assert result["is_anomaly"] is False


def test_master_miss_routes_to_hitl() -> None:
    """マスタキー不一致時は計算スキップしHITL対象に。"""
    result = calculate_commission(_sales_record(), {})

    assert result["master_found"] is False
    assert result["is_anomaly"] is True
    assert result["hitl_reason"] == "マスタキー不一致"
    assert result["total_commission"] == 0


def test_qi_split_calculation() -> None:
    """QI 適用範囲 / 分割計上期間で按分計算。"""
    master_entry = _master_entry(qi_scope=120000, qi_split_period=12)
    master = {master_entry["key"]: master_entry}
    result = calculate_commission(_sales_record(), master)

    # QI 120000 / 12 = 10000
    assert result["qi_amount"] == 10000


def test_return_skipped_for_initial_shipment() -> None:
    """ファイル区分が初回の場合は戻入計算をスキップ。"""
    master = {_master_entry()["key"]: _master_entry()}
    rec = _sales_record(**{"ファイル区分": "販売店_サーバー初回", "delivery_count": 1})
    result = calculate_commission(rec, master)

    assert result["return_amount"] == 0
    assert any("初回出荷のため戻入対象外" in s for s in result["calculation_trace"])


def test_return_full_for_continuing_under_threshold() -> None:
    """継続出荷で 12 本未満なら全額戻入 + 違約金。"""
    master_entry = _master_entry(penalty=5000)
    master = {master_entry["key"]: master_entry}
    rec = _sales_record(**{"ファイル区分": "販売店_サーバー継続", "delivery_count": 5})
    result = calculate_commission(rec, master)

    assert result["return_amount"] == -48750  # -(43750 + 5000)
    assert result["total_commission"] == -5000


def test_detect_anomalies_threshold() -> None:
    """高額アラート / マスタ未ヒット / 両方該当を抽出。"""
    results = [
        {"total_commission": 50_000, "master_found": True, "is_anomaly": False},
        {"total_commission": 200_000, "master_found": True, "is_anomaly": False},
        {
            "total_commission": 0,
            "master_found": False,
            "is_anomaly": True,
            "hitl_reason": "init",
        },
    ]
    pending = detect_anomalies(results, threshold=100_000)
    assert len(pending) == 2
    assert "高額アラート" in pending[0]["hitl_reason"]
    assert "マスタキー不一致" in pending[1]["hitl_reason"]


def test_generate_summary_aggregations() -> None:
    """サマリ集計が取引先・商材ごとに合算される。"""
    results = [
        {
            "total_commission": 40000,
            "partner_name": "A社",
            "product": "プラン1",
            "is_anomaly": False,
            "master_found": True,
        },
        {
            "total_commission": 30000,
            "partner_name": "A社",
            "product": "プラン2",
            "is_anomaly": False,
            "master_found": True,
        },
        {
            "total_commission": 0,
            "partner_name": "B社",
            "product": "プラン1",
            "is_anomaly": True,
            "master_found": False,
        },
    ]
    s = generate_summary(results)
    assert s["total_records"] == 3
    assert s["auto_completed"] == 2
    assert s["hitl_pending"] == 1
    assert s["total_commission_amount"] == 70000
    assert s["by_partner"][0]["name"] == "A社"
    assert s["by_partner"][0]["total"] == 70000


def test_make_lookup_key_format() -> None:
    """複合キーのフォーマット確認。"""
    key = make_lookup_key(
        partner_code=2019030136,
        application_month=datetime(2025, 11, 15),
        product="ずっとPREMIUMプラン",
        payment_method="クレジットカード",
    )
    assert key == "201903013620251101ずっとPREMIUMプランクレジットカード"
