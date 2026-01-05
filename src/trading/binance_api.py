"""Binance Futures API client with testnet support for paper trading.

This module provides a unified interface for trading on Binance Futures,
supporting both testnet (paper trading) and mainnet environments.
"""

import asyncio
import logging
from typing import Optional, Dict, List, Any
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from src.config_loader import CONFIG

class BinanceAPI:
    """Facade around Binance Futures API with async convenience methods.
    
    Supports both testnet (paper trading) and mainnet environments.
    Provides retry logic and consistent error handling for the trading agent.
    """
    
    def __init__(self):
        """Initialize Binance client with API credentials.
        
        Raises:
            ValueError: If API key or secret is missing from configuration.
        """
        api_key = CONFIG.get("binance_api_key")
        api_secret = CONFIG.get("binance_api_secret")
        
        if not api_key or not api_secret:
            raise ValueError("BINANCE_API_KEY and BINANCE_API_SECRET must be provided")
        
        # Determine if using testnet
        self.use_testnet = CONFIG.get("binance_testnet", True)
        
        # Initialize client
        if self.use_testnet:
            # Binance Futures Testnet
            self.client = Client(
                api_key=api_key,
                api_secret=api_secret,
                testnet=True
            )
            logging.info("🧪 Binance client initialized in TESTNET mode (paper trading)")
        else:
            # Binance Futures Mainnet
            self.client = Client(
                api_key=api_key,
                api_secret=api_secret
            )
            logging.warning("⚠️ Binance client initialized in MAINNET mode (REAL MONEY)")
        
        # Cache for market info
        self._exchange_info = None
        self._symbol_precision = {}
    
    async def _retry(self, fn, *args, max_attempts: int = 3, backoff_base: float = 0.5, **kwargs):
        """Retry helper with exponential backoff.
        
        Args:
            fn: Callable to invoke (will be run in thread pool).
            *args: Positional arguments forwarded to fn.
            max_attempts: Maximum number of attempts before raising exception.
            backoff_base: Initial delay in seconds, doubled after each failure.
            **kwargs: Keyword arguments forwarded to fn.
        
        Returns:
            Result produced by fn.
        
        Raises:
            Exception: Propagates any exception raised by fn after retries.
        """
        last_err = None
        for attempt in range(max_attempts):
            try:
                return await asyncio.to_thread(fn, *args, **kwargs)
            except (BinanceAPIException, BinanceRequestException, ConnectionError) as e:
                last_err = e
                logging.warning(
                    "Binance API call failed (attempt %s/%s): %s",
                    attempt + 1, max_attempts, e
                )
                if attempt < max_attempts - 1:
                    await asyncio.sleep(backoff_base * (2 ** attempt))
                continue
            except Exception as e:
                last_err = e
                logging.error("Unexpected error in Binance API call: %s", e)
                break
        
        raise last_err if last_err else RuntimeError("Binance retry: unknown error")
    
    def _get_symbol_precision(self, symbol: str) -> Dict[str, int]:
        """Get precision info for a symbol from cached exchange info.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT').
        
        Returns:
            Dict with 'quantity' and 'price' precision decimals.
        """
        if symbol in self._symbol_precision:
            return self._symbol_precision[symbol]
        
        # Default precision
        precision = {"quantity": 3, "price": 2}
        
        if self._exchange_info:
            for s in self._exchange_info.get("symbols", []):
                if s.get("symbol") == symbol:
                    # Extract precision from filters
                    for f in s.get("filters", []):
                        if f.get("filterType") == "LOT_SIZE":
                            step_size = f.get("stepSize", "0.001")
                            precision["quantity"] = len(step_size.rstrip('0').split('.')[-1])
                        elif f.get("filterType") == "PRICE_FILTER":
                            tick_size = f.get("tickSize", "0.01")
                            precision["price"] = len(tick_size.rstrip('0').split('.')[-1])
                    break
        
        self._symbol_precision[symbol] = precision
        return precision
    
    def _normalize_symbol(self, asset: str) -> str:
        """Convert asset symbol to Binance futures format.
        
        Args:
            asset: Asset symbol (e.g., 'BTC', 'ETH').
        
        Returns:
            Binance futures symbol (e.g., 'BTCUSDT').
        """
        asset = asset.upper().strip()
        if not asset.endswith("USDT"):
            asset = f"{asset}USDT"
        return asset
    
    def round_quantity(self, symbol: str, quantity: float) -> float:
        """Round quantity to symbol's precision.
        
        Args:
            symbol: Trading pair symbol.
            quantity: Quantity to round.
        
        Returns:
            Rounded quantity.
        """
        precision = self._get_symbol_precision(symbol)
        return round(quantity, precision["quantity"])
    
    def round_price(self, symbol: str, price: float) -> float:
        """Round price to symbol's precision.
        
        Args:
            symbol: Trading pair symbol.
            price: Price to round.
        
        Returns:
            Rounded price.
        """
        precision = self._get_symbol_precision(symbol)
        return round(price, precision["price"])
    
    async def get_exchange_info(self) -> Dict:
        """Fetch and cache exchange information.
        
        Returns:
            Exchange info dictionary.
        """
        if not self._exchange_info:
            self._exchange_info = await self._retry(self.client.futures_exchange_info)
        return self._exchange_info
    
    async def place_buy_order(self, asset: str, amount: float, slippage: float = 0.01) -> Dict:
        """Submit a market buy order (long position).
        
        Args:
            asset: Asset symbol to trade (e.g., 'BTC').
            amount: Quantity to buy.
            slippage: Not used for market orders, kept for API compatibility.
        
        Returns:
            Order response from Binance API.
        """
        symbol = self._normalize_symbol(asset)
        quantity = self.round_quantity(symbol, amount)
        
        logging.info(f"📈 Placing BUY order: {quantity} {symbol}")
        
        return await self._retry(
            self.client.futures_create_order,
            symbol=symbol,
            side="BUY",
            type="MARKET",
            quantity=quantity
        )
    
    async def place_sell_order(self, asset: str, amount: float, slippage: float = 0.01) -> Dict:
        """Submit a market sell order (short position).
        
        Args:
            asset: Asset symbol to trade (e.g., 'BTC').
            amount: Quantity to sell.
            slippage: Not used for market orders, kept for API compatibility.
        
        Returns:
            Order response from Binance API.
        """
        symbol = self._normalize_symbol(asset)
        quantity = self.round_quantity(symbol, amount)
        
        logging.info(f"📉 Placing SELL order: {quantity} {symbol}")
        
        return await self._retry(
            self.client.futures_create_order,
            symbol=symbol,
            side="SELL",
            type="MARKET",
            quantity=quantity
        )
    
    async def place_take_profit(self, asset: str, is_buy: bool, amount: float, tp_price: float) -> Dict:
        """Create a take-profit order.
        
        Args:
            asset: Asset symbol to trade.
            is_buy: True if original position is long (TP will be SELL).
            amount: Quantity to close.
            tp_price: Take-profit trigger price.
        
        Returns:
            Order response from Binance API.
        """
        symbol = self._normalize_symbol(asset)
        quantity = self.round_quantity(symbol, amount)
        price = self.round_price(symbol, tp_price)
        
        # For long position, TP is a SELL order; for short, TP is a BUY order
        side = "SELL" if is_buy else "BUY"
        
        logging.info(f"🎯 Placing TAKE_PROFIT order: {side} {quantity} {symbol} @ {price}")
        
        return await self._retry(
            self.client.futures_create_order,
            symbol=symbol,
            side=side,
            type="TAKE_PROFIT_MARKET",
            quantity=quantity,
            stopPrice=price,
            reduceOnly=True
        )
    
    async def place_stop_loss(self, asset: str, is_buy: bool, amount: float, sl_price: float) -> Dict:
        """Create a stop-loss order.
        
        Args:
            asset: Asset symbol to trade.
            is_buy: True if original position is long (SL will be SELL).
            amount: Quantity to close.
            sl_price: Stop-loss trigger price.
        
        Returns:
            Order response from Binance API.
        """
        symbol = self._normalize_symbol(asset)
        quantity = self.round_quantity(symbol, amount)
        price = self.round_price(symbol, sl_price)
        
        # For long position, SL is a SELL order; for short, SL is a BUY order
        side = "SELL" if is_buy else "BUY"
        
        logging.info(f"🛑 Placing STOP_LOSS order: {side} {quantity} {symbol} @ {price}")
        
        return await self._retry(
            self.client.futures_create_order,
            symbol=symbol,
            side=side,
            type="STOP_MARKET",
            quantity=quantity,
            stopPrice=price,
            reduceOnly=True
        )
    
    async def cancel_order(self, asset: str, order_id: int) -> Dict:
        """Cancel a specific order.
        
        Args:
            asset: Asset symbol.
            order_id: Order ID to cancel.
        
        Returns:
            Cancellation response.
        """
        symbol = self._normalize_symbol(asset)
        
        logging.info(f"❌ Cancelling order {order_id} for {symbol}")
        
        return await self._retry(
            self.client.futures_cancel_order,
            symbol=symbol,
            orderId=order_id
        )
    
    async def cancel_all_orders(self, asset: str) -> Dict:
        """Cancel all open orders for an asset.
        
        Args:
            asset: Asset symbol.
        
        Returns:
            Cancellation response.
        """
        symbol = self._normalize_symbol(asset)
        
        logging.info(f"❌ Cancelling all orders for {symbol}")
        
        return await self._retry(
            self.client.futures_cancel_all_open_orders,
            symbol=symbol
        )
    
    async def get_open_orders(self, asset: Optional[str] = None) -> List[Dict]:
        """Fetch open orders.
        
        Args:
            asset: Optional asset symbol to filter by.
        
        Returns:
            List of open orders.
        """
        if asset:
            symbol = self._normalize_symbol(asset)
            raw_orders = await self._retry(
                self.client.futures_get_open_orders,
                symbol=symbol
            )
        else:
            raw_orders = await self._retry(self.client.futures_get_open_orders)
            
        # Normalize to Hyperliquid format
        normalized = []
        for o in raw_orders:
            normalized.append({
                "coin": o.get('symbol'),
                "oid": o.get('orderId'),
                "isBuy": o.get('side') == 'BUY',
                "sz": o.get('origQty'),
                "px": o.get('price'),
                "triggerPx": o.get('stopPrice'),
                "orderType": o.get('type')
            })
        return normalized
    
    async def get_user_state(self) -> Dict:
        """Retrieve account balance and positions.
        
        Returns:
            Dictionary with 'balance', 'total_value', and 'positions'.
        """
        account = await self._retry(self.client.futures_account)
        
        # Extract balance
        balance = float(account.get("availableBalance", 0.0))
        total_value = float(account.get("totalWalletBalance", 0.0))
        
        # Extract positions
        positions = []
        for pos in account.get("positions", []):
            position_amt = float(pos.get("positionAmt", 0))
            if position_amt != 0:  # Only include active positions
                entry_price = float(pos.get("entryPrice", 0))
                unrealized_pnl = float(pos.get("unrealizedProfit", 0))
                
                positions.append({
                    "coin": pos.get("symbol"),
                    "szi": position_amt,
                    "entryPx": entry_price,
                    "pnl": unrealized_pnl,
                    "notional_entry": abs(position_amt) * entry_price,
                    "leverage": pos.get("leverage", "1"),
                    "liquidationPx": pos.get("liquidationPrice", "0")
                })
        
        return {
            "balance": balance,
            "total_value": total_value,
            "positions": positions
        }
    
    async def get_current_price(self, asset: str) -> float:
        """Get current market price for an asset.
        
        Args:
            asset: Asset symbol.
        
        Returns:
            Current price as float.
        """
        symbol = self._normalize_symbol(asset)
        ticker = await self._retry(
            self.client.futures_symbol_ticker,
            symbol=symbol
        )
        return float(ticker.get("price", 0.0))
    
    async def get_recent_fills(self, asset: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get recent trade fills.
        
        Args:
            asset: Optional asset symbol to filter by.
            limit: Maximum number of fills to return.
        
        Returns:
            List of recent fills.
        """
        if not asset:
            return []
            
        symbol = self._normalize_symbol(asset)
        raw_fills = await self._retry(
            self.client.futures_account_trades,
            symbol=symbol,
            limit=limit
        )
        
        # Normalize to Hyperliquid format
        normalized = []
        for f in raw_fills:
            normalized.append({
                "time": f.get('time'),
                "coin": f.get('symbol'),
                "isBuy": f.get('side') == 'BUY',
                "sz": f.get('qty'),
                "px": f.get('price')
            })
        return normalized
    
    async def set_leverage(self, asset: str, leverage: int) -> Dict:
        """Set leverage for a symbol.
        
        Args:
            asset: Asset symbol.
            leverage: Leverage multiplier (1-125).
        
        Returns:
            Response from API.
        """
        symbol = self._normalize_symbol(asset)
        
        logging.info(f"⚙️ Setting leverage to {leverage}x for {symbol}")
        
        return await self._retry(
            self.client.futures_change_leverage,
            symbol=symbol,
            leverage=leverage
        )
    
    async def set_margin_type(self, asset: str, margin_type: str = "CROSSED") -> Dict:
        """Set margin type for a symbol.
        
        Args:
            asset: Asset symbol.
            margin_type: 'CROSSED' or 'ISOLATED'.
        
        Returns:
            Response from API.
        """
        symbol = self._normalize_symbol(asset)
        
        logging.info(f"⚙️ Setting margin type to {margin_type} for {symbol}")
        
        try:
            return await self._retry(
                self.client.futures_change_margin_type,
                symbol=symbol,
                marginType=margin_type
            )
        except BinanceAPIException as e:
            # Ignore error if margin type is already set
            if "No need to change margin type" in str(e):
                logging.info(f"Margin type already set to {margin_type} for {symbol}")
                return {"msg": "Margin type already set"}
            raise
    
    async def get_open_interest(self, asset: str) -> Optional[float]:
        """Get open interest for an asset.
        
        Args:
            asset: Asset symbol.
        
        Returns:
            Open interest value or None if unavailable.
        """
        try:
            symbol = self._normalize_symbol(asset)
            oi_data = await self._retry(
                self.client.futures_open_interest,
                symbol=symbol
            )
            return float(oi_data.get("openInterest", 0)) if oi_data else None
        except Exception as e:
            logging.warning(f"Could not fetch open interest for {asset}: {e}")
            return None
    
    async def get_funding_rate(self, asset: str) -> Optional[float]:
        """Get current funding rate for an asset.
        
        Args:
            asset: Asset symbol.
        
        Returns:
            Funding rate as float or None if unavailable.
        """
        try:
            symbol = self._normalize_symbol(asset)
            ticker = await self._retry(
                self.client.futures_ticker,
                symbol=symbol
            )
            if ticker and isinstance(ticker, dict):
                return float(ticker.get("lastFundingRate", 0))
            return None
        except Exception as e:
            logging.warning(f"Could not fetch funding rate for {asset}: {e}")
            return None
    
    def extract_oids(self, order_result: Dict) -> List[int]:
        """Extract order IDs from an order response.
        
        Args:
            order_result: Order response from Binance API.
        
        Returns:
            List of order IDs.
        """
        oids = []
        try:
            # Binance returns orderId directly in the response
            if isinstance(order_result, dict) and "orderId" in order_result:
                oids.append(order_result["orderId"])
        except Exception as e:
            logging.warning(f"Could not extract order IDs: {e}")
        return oids
