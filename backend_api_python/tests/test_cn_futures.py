"""Tests for the Chinese futures data source (symbol handling only, no network)."""
from app.data_sources.cn_futures import (
    is_cn_futures_symbol,
    normalize_cn_futures_symbol,
)


def test_normalize_specific_contracts():
    assert normalize_cn_futures_symbol("P2701") == "P2701"
    assert normalize_cn_futures_symbol("p2701") == "P2701"
    assert normalize_cn_futures_symbol("AG2612") == "AG2612"
    assert normalize_cn_futures_symbol("RB2610") == "RB2610"


def test_normalize_continuous():
    assert normalize_cn_futures_symbol("P0") == "P0"
    assert normalize_cn_futures_symbol("OI0") == "OI0"
    assert normalize_cn_futures_symbol("SC0") == "SC0"


def test_normalize_czce_three_digit():
    # CZCE quotes contracts as YMM (OI701); Sina expects YYMM (OI2701)
    assert normalize_cn_futures_symbol("OI701") == "OI2701"
    assert normalize_cn_futures_symbol("TA701") == "TA2701"


def test_rejects_non_cn_symbols():
    for sym in ["GC", "SI", "CL", "ES", "ETH/USDT", "BTCUSDT", "AAPL", "", "P", "P01"]:
        assert normalize_cn_futures_symbol(sym) is None, sym
        assert not is_cn_futures_symbol(sym), sym


def test_accepts_cn_symbols():
    for sym in ["OI0", "NI2601", "IF0", "T2703", "SC2512"]:
        assert is_cn_futures_symbol(sym), sym
