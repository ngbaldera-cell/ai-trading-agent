"""Client helper for interacting with the TAAPI technical analysis API."""

import requests
import os
import time
import logging
from src.config_loader import CONFIG


class TAAPIClient:
    """Fetches TA indicators with retry/backoff semantics for resilience."""

    def __init__(self):
        """Initialize TAAPI credentials and base URL."""
        self.api_key = CONFIG["taapi_api_key"]
        self.base_url = "https://api.taapi.io/"
        # Cache with TTL
        self._cache = {}
        self._cache_ttl = 30  # seconds
    
    def _get_cached(self, cache_key: str):
        """Check if a cached value exists and is still valid."""
        if cache_key in self._cache:
            value, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                logging.info(f"🔄 TAAPI cache hit: {cache_key}")
                return value
        return None
    
    def _set_cache(self, cache_key: str, value):
        """Store a value in cache with current timestamp."""
        self._cache[cache_key] = (value, time.time())

    def _get_with_retry(self, url, params, retries=3, backoff=2.0):
        """Perform a GET request with exponential backoff retry logic, specifically handling 429."""
        indicator = url.split('/')[-1]  # Extract indicator name from URL
        logging.info(f"⏳ TAAPI requesting {indicator}...")
        for attempt in range(retries):
            # Small delay between requests
            time.sleep(0.5)
            
            try:
                resp = requests.get(url, params=params, timeout=10)
                
                if resp.status_code == 429:
                    wait = backoff * (2 ** attempt)
                    logging.warning(f"⚠️ TAAPI Rate Limit (429), waiting {wait}s before retry {attempt+1}/{retries}")
                    time.sleep(wait)
                    continue
                    
                resp.raise_for_status()
                return resp.json()
            except requests.HTTPError as e:
                if (e.response.status_code >= 500 or e.response.status_code == 429) and attempt < retries - 1:
                    wait = backoff * (2 ** attempt)
                    logging.warning(f"TAAPI {e.response.status_code}, retrying in {wait}s")
                    time.sleep(wait)
                else:
                    raise
            except requests.Timeout as e:
                if attempt < retries - 1:
                    wait = backoff * (2 ** attempt)
                    logging.warning(f"TAAPI timeout, retrying in {wait}s")
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError("Max retries exceeded")

    def get_indicators(self, asset, interval):
        """Return a curated bundle of intraday indicators for ``asset``."""
        # Normalize symbol: if asset already contains '/', use as-is, otherwise append '/USDT'
        symbol = asset if '/' in asset else f"{asset}/USDT"
        params = {
            "secret": self.api_key,
            "exchange": "binance",
            "symbol": symbol,
            "interval": interval
        }
        rsi_response = self._get_with_retry(f"{self.base_url}rsi", params)
        macd_response = self._get_with_retry(f"{self.base_url}macd", params)
        sma_response = self._get_with_retry(f"{self.base_url}sma", params)
        ema_response = self._get_with_retry(f"{self.base_url}ema", params)
        bbands_response = self._get_with_retry(f"{self.base_url}bbands", params)
        return {
            "rsi": rsi_response.get("value"),
            "macd": macd_response,
            "sma": sma_response.get("value"),
            "ema": ema_response.get("value"),
            "bbands": bbands_response
        }

    def get_historical_indicator(self, indicator, symbol, interval, results=10, params=None):
        """Fetch historical indicator data with optional overrides."""
        base_params = {
            "secret": self.api_key,
            "exchange": "binance",
            "symbol": symbol,
            "interval": interval,
            "results": results
        }
        if params:
            base_params.update(params)
        response = self._get_with_retry(f"{self.base_url}{indicator}", base_params)
        return response

    def fetch_series(self, indicator: str, symbol: str, interval: str, results: int = 10, params: dict | None = None, value_key: str = "value") -> list:
        """Fetch and normalize a historical indicator series.

        Args:
            indicator: TAAPI indicator slug (e.g. ``"ema"``).
            symbol: Market pair identifier (e.g. ``"BTC/USDT"``).
            interval: Candle interval requested from TAAPI.
            results: Number of datapoints to request.
            params: Additional TAAPI query parameters.
            value_key: Key to extract from the TAAPI response payload.

        Returns:
            List of floats rounded to 4 decimals, or an empty list on error.
        """
        try:
            data = self.get_historical_indicator(indicator, symbol, interval, results=results, params=params)
            if isinstance(data, dict):
                # Simple indicators: {"value": [1,2,3]}
                if value_key in data and isinstance(data[value_key], list):
                    return [round(v, 4) if isinstance(v, (int, float)) else v for v in data[value_key]]
                # Error response
                if "error" in data:
                    import logging
                    logging.error(f"TAAPI error for {indicator} {symbol} {interval}: {data.get('error')}")
                    return []
            return []
        except Exception as e:
            import logging
            logging.error(f"TAAPI fetch_series exception for {indicator}: {e}")
            return []

    def fetch_value(self, indicator: str, symbol: str, interval: str, params: dict | None = None, key: str = "value"):
        """Fetch a single indicator value for the latest candle."""
        try:
            base_params = {
                "secret": self.api_key,
                "exchange": "binance",
                "symbol": symbol,
                "interval": interval
            }
            if params:
                base_params.update(params)
            data = self._get_with_retry(f"{self.base_url}{indicator}", base_params)
            if isinstance(data, dict):
                val = data.get(key)
                return round(val, 4) if isinstance(val, (int, float)) else val
            return None
        except Exception:
            return None

    def get_bulk(self, symbol: str, interval: str, constructs: list[dict]) -> dict:
        """Fetch multiple indicators using TAAPI bulk POST endpoint.
        
        Uses the real /bulk endpoint to fetch all indicators in a single request.
        Much more efficient than individual calls.
        
        Args:
            symbol: Asset symbol (e.g., "BTC/USDT").
            interval: Timeframe (e.g., "4h").
            constructs: List of indicator definitions, e.g.,
                [{"indicator": "ema", "period": 20, "id": "ema20"}, ...]
        
        Returns:
            Dictionary mapping 'id' to result value/object.
        """
        # Build cache key for the whole bulk request
        cache_key = f"bulk:{symbol}:{interval}:{hash(frozenset(tuple(sorted(c.items())) for c in constructs))}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        # Build indicators list for bulk request
        indicators = []
        for construct in constructs:
            ind = {"indicator": construct.get("indicator")}
            # Add optional params like period
            for key, val in construct.items():
                if key not in ("indicator", "id"):
                    ind[key] = val
            # Use 'id' from construct if provided
            if "id" in construct:
                ind["id"] = construct["id"]
            indicators.append(ind)
        
        payload = {
            "secret": self.api_key,
            "construct": {
                "exchange": "binance",
                "symbol": symbol,
                "interval": interval,
                "indicators": indicators
            }
        }
        
        logging.info(f"📦 TAAPI bulk requesting {len(indicators)} indicators for {symbol} {interval}...")
        
        try:
            resp = requests.post(f"{self.base_url}bulk", json=payload, timeout=15)
            
            if resp.status_code == 429:
                logging.warning("⚠️ TAAPI bulk rate limit (429)")
                return {c.get("id", c.get("indicator")): None for c in constructs}
            
            resp.raise_for_status()
            data = resp.json()
            
            # Parse response: {"data": [{"id": "...", "result": {...}}, ...]}
            results = {}
            if "data" in data and isinstance(data["data"], list):
                for item in data["data"]:
                    if isinstance(item, dict):
                        uid = item.get("id", "unknown")
                        result = item.get("result", {})
                        # Extract value from result
                        if isinstance(result, dict) and "value" in result:
                            results[uid] = result["value"]
                        else:
                            results[uid] = result
            
            # Cache the results
            self._set_cache(cache_key, results)
            logging.info(f"✅ TAAPI bulk success: {len(results)} indicators")
            return results
            
        except Exception as e:
            logging.error(f"TAAPI bulk error: {e}")
            return {c.get("id", c.get("indicator")): None for c in constructs}

