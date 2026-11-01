"""
Chinese futures data source (fork addition).

Market data comes from Sina futures quotes via AkShare, covering SHFE, DCE,
CZCE, INE and CFFEX products. Quotes and K-lines only (research/backtest);
this module has no trading capability.

Symbol convention (Sina codes, uppercase):
- Main continuous: <PRODUCT>0, e.g. P0 (palm oil), OI0 (rapeseed oil),
  NI0 (nickel), AG0 (silver), SC0 (crude oil)
- Specific contract: <PRODUCT><YYMM>, e.g. P2701, OI2701, AG2612
- CZCE 3-digit form (OI701) is normalized to the 4-digit form (OI2701)

Timeframe support:
- 1D / 1W: daily bars (continuous and specific contracts); 1W resampled
- 1m / 5m / 15m / 30m / 1H: minute bars, specific contracts only
  (Sina caps one response at 1023 rows)
- 4H: resampled from 60-minute bars, specific contracts only
- Minute bars for continuous symbols are not offered by Sina and return []
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.data_sources.base import BaseDataSource
from app.utils.logger import get_logger

logger = get_logger(__name__)

CN_TZ = timezone(timedelta(hours=8))

# Chinese futures product codes (exchange codes, uppercase)
CN_FUTURES_PRODUCTS = {
    # SHFE
    "CU", "AL", "ZN", "PB", "NI", "SN", "AU", "AG", "RB", "WR", "HC",
    "SS", "BU", "RU", "SP", "FU", "AO", "BR", "AD", "OP",
    # INE
    "SC", "NR", "LU", "BC", "EC",
    # DCE
    "A", "B", "C", "CS", "EB", "EG", "I", "J", "JM", "L", "M", "P",
    "PP", "V", "Y", "PG", "BZ", "LG",
    # CZCE
    "OI", "CF", "FG", "TA", "MA", "SR", "RM", "AP", "CJ", "CY", "SA",
    "UR", "PF", "PK", "SH", "PX", "SM", "SF", "RI", "WH", "JR", "LR",
    "PM", "RS", "ZC",
    # CFFEX
    "IF", "IC", "IH", "IM", "T", "TS", "TF", "TL",
}

_SYMBOL_RE = re.compile(r"^([A-Z]{1,2})(\d{3,4}|0)$")

_MINUTE_PERIODS = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "1H": "60"}


def normalize_cn_futures_symbol(symbol: str) -> Optional[str]:
    """Normalize user input to a Sina code; None when not a CN futures symbol."""
    sym = (symbol or "").strip().upper().replace("=F", "")
    m = _SYMBOL_RE.match(sym)
    if not m:
        return None
    product, suffix = m.group(1), m.group(2)
    if product not in CN_FUTURES_PRODUCTS:
        return None
    if suffix == "0":
        return f"{product}0"
    if len(suffix) == 3:
        # CZCE 3-digit YMM -> 4-digit YYMM (current decade)
        suffix = "2" + suffix
    return f"{product}{suffix}"


def is_cn_futures_symbol(symbol: str) -> bool:
    return normalize_cn_futures_symbol(symbol) is not None


def _ts_from_date(text: str) -> int:
    dt = datetime.strptime(str(text)[:10], "%Y-%m-%d").replace(tzinfo=CN_TZ)
    return int(dt.timestamp())


def _ts_from_datetime(text: str) -> int:
    dt = datetime.strptime(str(text)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN_TZ)
    return int(dt.timestamp())


class CnFuturesDataSource(BaseDataSource):
    """Chinese futures quotes via AkShare/Sina."""

    name = "CnFutures"

    # ---- public interface ----------------------------------------------
    def get_kline(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        before_time: Optional[int] = None,
        after_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        sym = normalize_cn_futures_symbol(symbol)
        if not sym:
            return []
        tf = (timeframe or "1D").strip()
        try:
            if tf in ("1D", "1W"):
                bars = self._daily_bars(sym)
                if tf == "1W":
                    bars = self._resample_weekly(bars)
            elif tf in _MINUTE_PERIODS:
                bars = self._minute_bars(sym, _MINUTE_PERIODS[tf])
            elif tf == "4H":
                bars = self._resample_hours(self._minute_bars(sym, "60"), 4)
            else:
                logger.debug("CnFutures unsupported timeframe %s", tf)
                return []
        except Exception as e:
            logger.debug("CnFutures kline failed %s %s: %s", sym, tf, e)
            return []

        if after_time:
            bars = [b for b in bars if b["time"] >= int(after_time)]
        if before_time:
            bars = [b for b in bars if b["time"] <= int(before_time)]
        if limit and len(bars) > limit:
            bars = bars[-int(limit):]
        return bars

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        sym = normalize_cn_futures_symbol(symbol)
        if not sym:
            return {"symbol": symbol, "last": 0.0}
        try:
            bars = self._daily_bars(sym)
            if bars:
                last = bars[-1]
                return {
                    "symbol": sym,
                    "last": float(last["close"]),
                    "source": "akshare_sina",
                    "timestamp": int(last["time"]),
                }
        except Exception as e:
            logger.debug("CnFutures ticker failed %s: %s", sym, e)
        return {"symbol": sym, "last": 0.0}

    # ---- fetching --------------------------------------------------------
    def _daily_bars(self, sym: str) -> List[Dict[str, Any]]:
        import akshare as ak

        if sym.endswith("0"):
            df = ak.futures_main_sina(symbol=sym)
            cols = {c: i for i, c in enumerate(df.columns)}
            return [
                self.format_kline(
                    _ts_from_date(r[cols["日期"]]),
                    r[cols["开盘价"]], r[cols["最高价"]], r[cols["最低价"]],
                    r[cols["收盘价"]], r[cols["成交量"]],
                )
                for r in df.itertuples(index=False)
            ]
        df = ak.futures_zh_daily_sina(symbol=sym)
        return [
            self.format_kline(
                _ts_from_date(r.date), r.open, r.high, r.low, r.close, r.volume
            )
            for r in df.itertuples(index=False)
        ]

    def _minute_bars(self, sym: str, period: str) -> List[Dict[str, Any]]:
        if sym.endswith("0"):
            # Sina minute bars exist for specific contracts only
            logger.debug("CnFutures minute bars unavailable for continuous %s", sym)
            return []
        import akshare as ak

        df = ak.futures_zh_minute_sina(symbol=sym, period=period)
        return [
            self.format_kline(
                _ts_from_datetime(r.datetime), r.open, r.high, r.low,
                r.close, r.volume,
            )
            for r in df.itertuples(index=False)
        ]

    # ---- resampling ------------------------------------------------------
    @staticmethod
    def _resample_weekly(bars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        cur: Optional[Dict[str, Any]] = None
        cur_key: Optional[Any] = None
        for b in bars:
            d = datetime.fromtimestamp(b["time"], tz=CN_TZ)
            key = d.isocalendar()[:2]
            if key != cur_key:
                if cur:
                    out.append(cur)
                cur = dict(b)
                cur_key = key
            else:
                cur["high"] = max(cur["high"], b["high"])
                cur["low"] = min(cur["low"], b["low"])
                cur["close"] = b["close"]
                cur["volume"] = round(cur["volume"] + b["volume"], 2)
        if cur:
            out.append(cur)
        return out

    @staticmethod
    def _resample_hours(bars: List[Dict[str, Any]], hours: int) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        cur: Optional[Dict[str, Any]] = None
        cur_key: Optional[Any] = None
        span = hours * 3600
        for b in bars:
            key = b["time"] // span
            if key != cur_key:
                if cur:
                    out.append(cur)
                cur = dict(b)
                cur_key = key
            else:
                cur["high"] = max(cur["high"], b["high"])
                cur["low"] = min(cur["low"], b["low"])
                cur["close"] = b["close"]
                cur["volume"] = round(cur["volume"] + b["volume"], 2)
        if cur:
            out.append(cur)
        return out
