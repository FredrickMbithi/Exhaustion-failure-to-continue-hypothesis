"""
Multi-provider FX data downloader with provenance tracking.

Supports OANDA (REST) and Dukascopy (CSV feed) downloads and writes
sidecar provenance metadata so datasets can be audited later.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import requests


@dataclass
class DataProvenance:
    """Record of where/how data was sourced."""

    provider: str
    symbol: str
    start: str
    end: str
    granularity: str
    timezone: str
    source_url: Optional[str]
    downloaded_at: str
    rows: int
    notes: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def _write_with_provenance(
    df: pd.DataFrame,
    output_path: str,
    provenance: DataProvenance
) -> Tuple[str, str]:
    """
    Persist dataset to CSV and sidecar provenance JSON.

    Returns:
        Tuple of (csv_path, provenance_path)
    """
    csv_path = Path(output_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path)

    prov_path = csv_path.with_suffix(csv_path.suffix + ".prov.json")
    prov_path.write_text(provenance.to_json())
    return str(csv_path), str(prov_path)


def download_oanda_data(
    symbol: str,
    start_date: str,
    end_date: str,
    granularity: str = "D",
    price: str = "M",
    api_token: Optional[str] = None,
    account_type: str = "practice",
    output_path: Optional[str] = None,
) -> Tuple[pd.DataFrame, Optional[DataProvenance]]:
    """
    Download OHLC data from the OANDA v3 REST API.

    Notes:
        - Requires environment variable OANDA_API_KEY if api_token not passed.
        - This function is network-bound; wrap in try/except in production.
        - Returned DataFrame is indexed by UTC timestamps.
    """
    token = api_token or os.getenv("OANDA_API_KEY")
    if token is None:
        # Graceful fallback for offline runs
        raise RuntimeError("OANDA API token not provided (set OANDA_API_KEY).")

    domain = "api-fxpractice.oanda.com" if account_type == "practice" else "api-fxtrade.oanda.com"
    url = f"https://{domain}/v3/instruments/{symbol}/candles"

    params = {
        "granularity": granularity,
        "price": price,
        "from": pd.to_datetime(start_date).tz_localize("UTC").isoformat(),
        "to": pd.to_datetime(end_date).tz_localize("UTC").isoformat(),
    }
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    candles = payload.get("candles", [])
    if not candles:
        raise RuntimeError(f"OANDA returned no candles for {symbol}")

    records = []
    for c in candles:
        record = {
            "timestamp": pd.to_datetime(c["time"]),
            "open": float(c["mid"]["o"]),
            "high": float(c["mid"]["h"]),
            "low": float(c["mid"]["l"]),
            "close": float(c["mid"]["c"]),
            "volume": float(c.get("volume", 0)),
        }
        records.append(record)

    df = pd.DataFrame(records).set_index("timestamp").sort_index()
    df.index = df.index.tz_convert("UTC")

    provenance = DataProvenance(
        provider="OANDA",
        symbol=symbol,
        start=start_date,
        end=end_date,
        granularity=granularity,
        timezone="UTC",
        source_url=url,
        downloaded_at=datetime.utcnow().isoformat(),
        rows=len(df),
        notes="mid prices; volume is broker tick volume",
    )

    if output_path:
        _write_with_provenance(df, output_path, provenance)

    return df, provenance


def download_dukascopy_data(
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str = "D",
    output_path: Optional[str] = None,
    csv_url: Optional[str] = None,
) -> Tuple[pd.DataFrame, Optional[DataProvenance]]:
    """
    Download Dukascopy data (CSV feed).

    Dukascopy provides gzipped CSV files per instrument/timeframe; here we
    allow passing a direct CSV URL (useful for mirrors) or raise a clear
    error so the caller can handle offline scenarios.
    """
    if csv_url is None:
        raise RuntimeError("Provide csv_url for Dukascopy download (mirror required).")

    resp = requests.get(csv_url, timeout=60)
    resp.raise_for_status()

    df = pd.read_csv(csv_url, parse_dates=["timestamp"])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.set_index('timestamp').sort_index()

    # Clip to requested range
    df = df.loc[pd.to_datetime(start_date): pd.to_datetime(end_date)]

    provenance = DataProvenance(
        provider="Dukascopy",
        symbol=symbol,
        start=start_date,
        end=end_date,
        granularity=timeframe,
        timezone="UTC",
        source_url=csv_url,
        downloaded_at=datetime.utcnow().isoformat(),
        rows=len(df),
        notes="Data pulled from Dukascopy CSV mirror",
    )

    if output_path:
        _write_with_provenance(df, output_path, provenance)

    return df, provenance
