"""Entry-point script that wires together the trading agent, data feeds, and API."""

import sys
import argparse
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))
from src.agent.decision_maker import TradingAgent
from src.indicators.taapi_client import TAAPIClient
import asyncio
import logging
from collections import deque, OrderedDict
from datetime import datetime, timezone
import math  # For Sharpe
from dotenv import load_dotenv
import os
import json
from aiohttp import web
from src.utils.formatting import format_number as fmt, format_size as fmt_sz
from src.utils.prompt_utils import json_default, round_or_none, round_series
from src.utils.trade_stats import calculate_performance, get_trade_history
from src.prompt_manager import PromptManager

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def clear_terminal():
    """Clear the terminal screen on Windows or POSIX systems."""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_interval_seconds(interval_str):
    """Convert interval strings like '5m' or '1h' to seconds."""
    interval_str = interval_str.strip().strip('"\'')  # Strip quotes
    if interval_str.endswith('m'):
        return int(interval_str[:-1]) * 60
    elif interval_str.endswith('h'):
        return int(interval_str[:-1]) * 3600
    elif interval_str.endswith('d'):
        return int(interval_str[:-1]) * 86400
    else:
        raise ValueError(f"Unsupported interval: {interval_str}")


def normalize_symbol(asset):
    """Normalize asset name to TAAPI symbol format (e.g., BTC -> BTC/USDT, XRP/USDT -> XRP/USDT)."""
    asset = asset.strip().strip('"\'')
    if '/' in asset:
        # Already in symbol format, return as-is
        return asset
    else:
        # Append /USDT if not present
        return f"{asset}/USDT"

CONFIG_FILE = "config.json"

def load_runtime_config_file():
    """Load runtime config from JSON file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load {CONFIG_FILE}: {e}")
    return {}

def save_runtime_config_file(config):
    """Save runtime config to JSON file."""
    try:
        # Save a clean version without internal keys if any
        to_save = {
            "assets": config.get("assets", []),
            "interval": config.get("interval", "1h"),
            "leverage": config.get("leverage", 20),
            "risk_config": config.get("risk_config", {})
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(to_save, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save {CONFIG_FILE}: {e}")

def main():
    """Parse CLI args, bootstrap dependencies, and launch the trading loop."""
    clear_terminal()
    parser = argparse.ArgumentParser(description="LLM-based Trading Agent")
    parser.add_argument("--assets", type=str, nargs="+", required=False, help="Assets to trade, e.g., BTC ETH")
    parser.add_argument("--interval", type=str, required=False, help="Interval period, e.g., 1h")
    args = parser.parse_args()

    # Allow assets/interval via .env (CONFIG) if CLI not provided
    from src.config_loader import CONFIG
    
    # Initialize the appropriate exchange API
    exchange_name = CONFIG.get("exchange", "hyperliquid").lower()
    
    if exchange_name == "binance":
        from src.trading.binance_api import BinanceAPI
        exchange_api = BinanceAPI()
        logging.info("🔄 Using Binance exchange")
    elif exchange_name == "hyperliquid":
        from src.trading.hyperliquid_api import HyperliquidAPI
        exchange_api = HyperliquidAPI()
        logging.info("🔄 Using Hyperliquid exchange")
    else:
        raise ValueError(f"Unsupported exchange: {exchange_name}. Use 'binance' or 'hyperliquid'")
    
    # For backward compatibility, keep 'hyperliquid' variable name
    hyperliquid = exchange_api
    
    # Load persistent config
    saved_config = load_runtime_config_file()

    # Get env vars for fallback
    assets_env = CONFIG.get("assets")
    interval_env = CONFIG.get("interval")
    
    # 1. Assets: CLI -> Config -> Env -> Error
    final_assets = []
    if args.assets:
        final_assets = args.assets
    elif saved_config.get("assets"):
        final_assets = saved_config["assets"]
    elif assets_env:
         if "," in assets_env:
            final_assets = [a.strip().strip('"\'') for a in assets_env.split(",") if a.strip()]
         else:
            final_assets = [a.strip().strip('"\'') for a in assets_env.split(" ") if a.strip()]
    
    if not final_assets:
        parser.error("Please provide --assets, set ASSETS in .env, or ensure config.json exists.")

    # 2. Interval: CLI -> Config -> Env -> Error
    final_interval = None
    if args.interval:
        final_interval = args.interval.strip().strip('"\'')
    elif saved_config.get("interval"):
        final_interval = saved_config["interval"]
    elif interval_env:
        final_interval = interval_env.strip().strip('"\'')
        
    if not final_interval:
         parser.error("Please provide --interval, set INTERVAL in .env, or ensure config.json exists.")

    # 3. Leverage / Risk: Config -> Default
    final_leverage = saved_config.get("leverage", 20)
    final_risk = saved_config.get("risk_config", {
        "level": "conservative",
        "risk_per_trade": 1.0, 
        "max_daily_loss": 3.0,
        "max_simultaneous_trades": 2,
        "max_position_size_pct": 10.0
    })

    # Update config file if CLI args differ or new config created
    should_save = False
    if saved_config.get("assets") != final_assets:
        should_save = True
    if saved_config.get("interval") != final_interval:
        should_save = True
        
    runtime_config = {
        "assets": final_assets,
        "interval": final_interval,
        "leverage": final_leverage, 
        "risk_config": final_risk
    }
    
    if should_save:
        print("💾 Updating config.json from CLI arguments...")
        save_runtime_config_file(runtime_config)

    taapi = TAAPIClient()
    prompt_manager = PromptManager("prompts.json")
    agent = TradingAgent()
    agent.set_system_prompt(prompt_manager.get_current_prompt())


    start_time = datetime.now(timezone.utc)
    invocation_count = 0
    trade_log = []  # For Sharpe: list of returns
    active_trades = []  # {'asset','is_long','amount','entry_price','tp_oid','sl_oid','exit_plan'}
    recent_events = deque(maxlen=200)
    diary_path = "diary.jsonl"
    initial_account_value = None
    # Perp mid-price history sampled each loop (authoritative, avoids spot/perp basis mismatch)
    price_history = {}
    bot_paused = False  # Start RUNNING by default - safer for active trade management
    next_run_timestamp = None  # To track countdown
    current_data_quality = {}  # Store latest data quality per asset for dashboard

    AVAILABLE_ASSETS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK", "MATIC", "UNI", "ATOM", "LTC", "NEAR"]
    AVAILABLE_INTERVALS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
    AVAILABLE_LEVERAGES = [1, 2, 3, 5, 10, 20, 50, 75, 100, 125]

    print(f"Starting trading agent for assets: {runtime_config['assets']} at interval: {runtime_config['interval']}")
    print(f"🚀 Bot iniciado en modo ACTIVO. Dashboard: http://localhost:3000")
    print(f"🌐 Dashboard: http://localhost:3000")

    def add_event(msg: str):
        """Log an informational event and push it into the recent events deque."""
        logging.info(msg)

    async def detect_trade_outcome(trade: dict, fills: list, current_price: float) -> dict:
        """
        Determine how a trade closed by analyzing recent fills.
        Returns: {"outcome": "tp_hit"|"sl_hit"|"manual_close", "exit_price": float, "pnl_pct": float}
        """
        asset = trade.get('asset')
        entry_price = trade.get('entry_price', 0)
        is_long = trade.get('is_long', True)
        tp_price = trade.get('tp_price')
        sl_price = trade.get('sl_price')
        
        # Find exit fill for this asset (check both formats)
        exit_fill = None
        for fill in reversed(fills):
            coin = fill.get('coin') or fill.get('asset')
            if coin == asset or coin == f"{asset}USDT":
                exit_fill = fill
                break
        
        exit_price = current_price
        if exit_fill:
            exit_price = float(exit_fill.get('px') or exit_fill.get('price') or current_price)
        
        # Calculate PnL percentage
        if entry_price and entry_price > 0:
            if is_long:
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            else:
                pnl_pct = ((entry_price - exit_price) / entry_price) * 100
        else:
            pnl_pct = 0
        
        # Determine outcome based on proximity to TP/SL
        tolerance = 0.002  # 0.2% tolerance
        outcome = "manual_close"
        
        if tp_price and tp_price > 0:
            if abs(exit_price - tp_price) / tp_price < tolerance:
                outcome = "tp_hit"
        if sl_price and sl_price > 0:
            if abs(exit_price - sl_price) / sl_price < tolerance:
                outcome = "sl_hit"
        
        return {"outcome": outcome, "exit_price": round(exit_price, 2), "pnl_pct": round(pnl_pct, 2)}

    async def run_loop():
        """Main trading loop that gathers data, calls the agent, and executes trades."""
        nonlocal invocation_count, initial_account_value, bot_paused, next_run_timestamp
        interval_seconds = get_interval_seconds(runtime_config["interval"])
        while True:
            # If paused, go directly to the countdown/wait loop at the end (which handles pause correctly)
            if bot_paused:
                # Still need to update next_run_timestamp and check for interval changes while paused
                current_interval_seconds = interval_seconds
                for i in range(current_interval_seconds):
                    next_run_timestamp = (datetime.now(timezone.utc).timestamp() + (current_interval_seconds - i)) * 1000
                    new_interval_val = get_interval_seconds(runtime_config["interval"])
                    if new_interval_val != current_interval_seconds:
                        add_event(f"🔄 Interval changed detected ({current_interval_seconds}s -> {new_interval_val}s).")
                        interval_seconds = new_interval_val
                        current_interval_seconds = new_interval_val
                        break
                    await asyncio.sleep(1)
                    if not bot_paused:  # If resumed mid-wait, break to start trading
                        break
                interval_seconds = get_interval_seconds(runtime_config["interval"])
                continue
            
            invocation_count += 1
            add_event(f"🚀 Starting trading cycle #{invocation_count}")
            minutes_since_start = (datetime.now(timezone.utc) - start_time).total_seconds() / 60

            # Global account state
            state = await hyperliquid.get_user_state()
            total_value = state.get('total_value') or state['balance'] + sum(p.get('pnl', 0) for p in state['positions'])
            sharpe = calculate_sharpe(trade_log)

            account_value = total_value
            if initial_account_value is None:
                initial_account_value = account_value
            total_return_pct = ((account_value - initial_account_value) / initial_account_value * 100.0) if initial_account_value else 0.0

            positions = []
            for pos_wrap in state['positions']:
                pos = pos_wrap
                coin = pos.get('coin')
                current_px = await hyperliquid.get_current_price(coin) if coin else None
                positions.append({
                    "symbol": coin,
                    "quantity": round_or_none(pos.get('szi'), 6),
                    "entry_price": round_or_none(pos.get('entryPx'), 2),
                    "current_price": round_or_none(current_px, 2),
                    "liquidation_price": round_or_none(pos.get('liquidationPx') or pos.get('liqPx'), 2),
                    "unrealized_pnl": round_or_none(pos.get('pnl'), 4),
                    "leverage": pos.get('leverage')
                })

            recent_diary = []
            try:
                with open(diary_path, "r") as f:
                    lines = f.readlines()
                    for line in lines[-5:]:  # Reduced from 10 to 5 to save tokens
                        entry = json.loads(line)
                        recent_diary.append(entry)
            except Exception:
                pass

            open_orders_struct = []
            try:
                open_orders = await hyperliquid.get_open_orders()
                for o in open_orders[:10]:  # Reduced from 50 to 10 to save tokens
                    open_orders_struct.append({
                        "coin": o.get('coin'),
                        "oid": o.get('oid'),
                        "is_buy": o.get('isBuy'),
                        "size": round_or_none(o.get('sz'), 6),
                        "price": round_or_none(o.get('px'), 2),
                        "trigger_price": round_or_none(o.get('triggerPx'), 2),
                        "order_type": o.get('orderType')
                    })
            except Exception:
                open_orders = []

            # Reconcile active trades with outcome detection
            try:
                assets_with_positions = set()
                for pos in state['positions']:
                    try:
                        if abs(float(pos.get('szi') or 0)) > 0:
                            assets_with_positions.add(pos.get('coin'))
                    except Exception:
                        continue
                assets_with_orders = {o.get('coin') for o in (open_orders or []) if o.get('coin')}
                
                # Get recent fills for outcome detection
                recent_fills_for_outcome = []
                try:
                    recent_fills_for_outcome = await hyperliquid.get_recent_fills(limit=50)
                except Exception:
                    pass
                
                for tr in active_trades[:]:
                    asset = tr.get('asset')
                    # Check both asset name formats
                    asset_in_positions = asset in assets_with_positions or f"{asset}USDT" in assets_with_positions
                    asset_in_orders = asset in assets_with_orders or f"{asset}USDT" in assets_with_orders
                    
                    if not asset_in_positions and not asset_in_orders:
                        # Trade closed - detect outcome
                        current_px = await hyperliquid.get_current_price(asset)
                        outcome_info = await detect_trade_outcome(tr, recent_fills_for_outcome, current_px or 0)
                        
                        add_event(f"📊 Trade closed: {asset} | Outcome: {outcome_info['outcome']} | PnL: {outcome_info['pnl_pct']}%")
                        active_trades.remove(tr)
                        
                        # Write enhanced diary entry with outcome
                        with open(diary_path, "a") as f:
                            f.write(json.dumps({
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "asset": asset,
                                "action": "close",
                                "outcome": outcome_info["outcome"],
                                "entry_price": tr.get('entry_price'),
                                "exit_price": outcome_info["exit_price"],
                                "pnl_pct": outcome_info["pnl_pct"],
                                "is_long": tr.get('is_long'),
                                "tp_price": tr.get('tp_price'),
                                "sl_price": tr.get('sl_price'),
                                "opened_at": tr.get('opened_at'),
                                "exit_plan": tr.get('exit_plan')
                            }) + "\n")
            except Exception as e:
                add_event(f"Reconciliation error: {e}")

            recent_fills_struct = []
            try:
                fills = await hyperliquid.get_recent_fills(limit=50)
                for f_entry in fills[-5:]:  # Reduced from 20 to 5 to save tokens
                    try:
                        t_raw = f_entry.get('time') or f_entry.get('timestamp')
                        timestamp = None
                        if t_raw is not None:
                            try:
                                t_int = int(t_raw)
                                if t_int > 1e12:
                                    timestamp = datetime.fromtimestamp(t_int / 1000, tz=timezone.utc).isoformat()
                                else:
                                    timestamp = datetime.fromtimestamp(t_int, tz=timezone.utc).isoformat()
                            except Exception:
                                timestamp = str(t_raw)
                        recent_fills_struct.append({
                            "timestamp": timestamp,
                            "coin": f_entry.get('coin') or f_entry.get('asset'),
                            "is_buy": f_entry.get('isBuy'),
                            "size": round_or_none(f_entry.get('sz') or f_entry.get('size'), 6),
                            "price": round_or_none(f_entry.get('px') or f_entry.get('price'), 2)
                        })
                    except Exception:
                        continue
            except Exception:
                pass

            dashboard = {
                "total_return_pct": round(total_return_pct, 2),
                "balance": round_or_none(state['balance'], 2),
                "account_value": round_or_none(account_value, 2),
                "sharpe_ratio": round_or_none(sharpe, 3),
                "positions": positions,
                "active_trades": [
                    {
                        "asset": tr.get('asset'),
                        "is_long": tr.get('is_long'),
                        "amount": round_or_none(tr.get('amount'), 6),
                        "entry_price": round_or_none(tr.get('entry_price'), 2),
                        "tp_oid": tr.get('tp_oid'),
                        "sl_oid": tr.get('sl_oid'),
                        "exit_plan": tr.get('exit_plan'),
                        "opened_at": tr.get('opened_at')
                    }
                    for tr in active_trades
                ],
                "open_orders": open_orders_struct,
                "recent_diary": recent_diary,
                "recent_fills": recent_fills_struct,
            }

            # Gather data for ALL assets first
            market_sections = []
            asset_prices = {}
            for asset in runtime_config["assets"]:
                add_event(f"📊 Gathering data for {asset}...")
                try:
                    current_price = await hyperliquid.get_current_price(asset)
                    asset_prices[asset] = current_price
                    if asset not in price_history:
                        price_history[asset] = deque(maxlen=60)
                    price_history[asset].append({"t": datetime.now(timezone.utc).isoformat(), "mid": round_or_none(current_price, 2)})
                    oi = await hyperliquid.get_open_interest(asset)
                    funding = await hyperliquid.get_funding_rate(asset)

                    intraday_tf = runtime_config["interval"]
                    symbol = normalize_symbol(asset)
                    
                    # Use bulk endpoint for ALL intraday indicators (single call)
                    intraday_constructs = [
                        {"indicator": "ema", "period": 20, "id": "ema20"},
                        {"indicator": "macd", "id": "macd"},
                        {"indicator": "rsi", "period": 7, "id": "rsi7"},
                        {"indicator": "rsi", "period": 14, "id": "rsi14"}
                    ]
                    bulk_intraday = taapi.get_bulk(symbol, intraday_tf, intraday_constructs)
                    
                    # Extract intraday values (bulk returns single values, not series)
                    ema_series = [bulk_intraday.get("ema20")] if bulk_intraday.get("ema20") else []
                    macd_val = bulk_intraday.get("macd")
                    macd_series = [macd_val.get("valueMACD") if isinstance(macd_val, dict) else macd_val] if macd_val else []
                    rsi7_series = [bulk_intraday.get("rsi7")] if bulk_intraday.get("rsi7") else []
                    rsi14_series = [bulk_intraday.get("rsi14")] if bulk_intraday.get("rsi14") else []

                    # Use bulk endpoint for ALL 4h long-term indicators (single call)
                    bulk_4h_constructs = [
                        {"indicator": "ema", "period": 20, "id": "ema20"},
                        {"indicator": "ema", "period": 50, "id": "ema50"},
                        {"indicator": "atr", "period": 3, "id": "atr3"},
                        {"indicator": "atr", "period": 14, "id": "atr14"},
                        {"indicator": "macd", "id": "macd"},
                        {"indicator": "rsi", "period": 14, "id": "rsi14"}
                    ]
                    bulk_4h = taapi.get_bulk(symbol, "4h", bulk_4h_constructs)
                    
                    lt_ema20 = bulk_4h.get("ema20")
                    lt_ema50 = bulk_4h.get("ema50")
                    lt_atr3 = bulk_4h.get("atr3")
                    lt_atr14 = bulk_4h.get("atr14")
                    lt_macd = bulk_4h.get("macd")
                    lt_macd_series = [lt_macd.get("valueMACD") if isinstance(lt_macd, dict) else lt_macd] if lt_macd else []
                    lt_rsi_series = [bulk_4h.get("rsi14")] if bulk_4h.get("rsi14") else []

                    recent_mids = [entry["mid"] for entry in list(price_history.get(asset, []))[-5:]]  # Reduced from 10 to 5
                    funding_annualized = round(funding * 24 * 365 * 100, 2) if funding else None

                    # Data quality tracking
                    missing_indicators = []
                    if not ema_series:
                        missing_indicators.append("ema20")
                    if not macd_series:
                        missing_indicators.append("macd")
                    if not rsi7_series:
                        missing_indicators.append("rsi7")
                    if not rsi14_series:
                        missing_indicators.append("rsi14")
                    if lt_ema20 is None:
                        missing_indicators.append("4h_ema20")
                    if lt_ema50 is None:
                        missing_indicators.append("4h_ema50")
                    if lt_atr3 is None:
                        missing_indicators.append("4h_atr3")
                    if lt_atr14 is None:
                        missing_indicators.append("4h_atr14")
                    
                    total_indicators = 8
                    confidence = round((total_indicators - len(missing_indicators)) / total_indicators, 2)
                    data_status = "complete" if not missing_indicators else ("degraded" if confidence >= 0.5 else "failed")
                    
                    if missing_indicators:
                        add_event(f"⚠️ {asset} data {data_status}: missing {', '.join(missing_indicators)}")

                    market_sections.append({
                        "asset": asset,
                        "current_price": round_or_none(current_price, 2),
                        "data_quality": {
                            "status": data_status,
                            "missing": missing_indicators,
                            "confidence": confidence
                        },
                        "intraday": {
                            "ema20": round_or_none(ema_series[-1], 2) if ema_series else None,
                            "macd": round_or_none(macd_series[-1], 2) if macd_series else None,
                            "rsi7": round_or_none(rsi7_series[-1], 2) if rsi7_series else None,
                            "rsi14": round_or_none(rsi14_series[-1], 2) if rsi14_series else None,
                            "series": {
                                "ema20": round_series(ema_series, 2),
                                "macd": round_series(macd_series, 2),
                                "rsi7": round_series(rsi7_series, 2),
                                "rsi14": round_series(rsi14_series, 2)
                            }
                        },
                        "long_term": {
                            "ema20": round_or_none(lt_ema20, 2),
                            "ema50": round_or_none(lt_ema50, 2),
                            "atr3": round_or_none(lt_atr3, 2),
                            "atr14": round_or_none(lt_atr14, 2),
                            "macd_series": round_series(lt_macd_series, 2),
                            "rsi_series": round_series(lt_rsi_series, 2)
                        },
                        "open_interest": round_or_none(oi, 2),
                        "funding_rate": round_or_none(funding, 8),
                        "funding_annualized_pct": funding_annualized,
                        "recent_mid_prices": recent_mids
                    })
                    
                    # Store for Data Health API
                    current_data_quality[asset] = {
                        "status": data_status,
                        "missing": missing_indicators,
                        "confidence": confidence,
                        "updated": datetime.now(timezone.utc).isoformat()
                    }
                except Exception as e:
                    add_event(f"Data gather error {asset}: {e}")
                    current_data_quality[asset] = {"status": "failed", "missing": ["ALL"], "confidence": 0, "error": str(e)}
                    continue

            # Calculate performance stats for LLM feedback
            perf_stats = calculate_performance(diary_path)

            # Single LLM call with all assets
            context_payload = OrderedDict([
                ("invocation", {
                    "minutes_since_start": round(minutes_since_start, 2),
                    "current_time": datetime.now(timezone.utc).isoformat(),
                    "invocation_count": invocation_count
                }),
                ("performance_feedback", perf_stats),
                ("risk_parameters", runtime_config.get("risk_config", {})),
                ("account", dashboard),
                ("market_data", market_sections),
                ("instructions", {
                    "assets": runtime_config["assets"],
                    "requirement": "Decide actions for all assets and return a strict JSON array matching the schema."
                })
            ])
            context = json.dumps(context_payload, default=json_default)
            add_event(f"Combined prompt length: {len(context) if context else 0} chars for {len(runtime_config['assets'])} assets")
            with open("prompts.log", "a") as f:
                f.write(f"\n\n--- {datetime.now()} - ALL ASSETS ---\n{json.dumps(context_payload, indent=2, default=json_default)}\n")

            def _is_failed_outputs(outs):
                """Return True when outputs are missing or clearly invalid."""
                if not isinstance(outs, dict):
                    return True
                decisions = outs.get("trade_decisions")
                if not isinstance(decisions, list) or not decisions:
                    return True
                try:
                    return all(
                        isinstance(o, dict)
                        and (o.get('action') == 'hold')
                        and ('parse error' in (o.get('rationale', '').lower()))
                        for o in decisions
                    )
                except Exception:
                    return True

            try:
                # Pass runtime_config and account for variable injection
                add_event("🤖 Sending context to LLM...")
                outputs = agent.get_decisions(
                    context=context, 
                    assets=runtime_config["assets"],
                    config=runtime_config, 
                    account_data=state  # Fixed: was 'account' which doesn't exist
                )
                add_event(f"✅ LLM responded with {len(outputs.get('trade_decisions', []))} decisions" if isinstance(outputs, dict) else f"❌ Invalid LLM output: {type(outputs)}")
                if not isinstance(outputs, dict):
                    add_event(f"Invalid output format (expected dict): {outputs}")
                    outputs = {}
            except Exception as e:
                import traceback
                add_event(f"Agent error: {e}")
                add_event(f"Traceback: {traceback.format_exc()}")
                outputs = {}

            # Retry once on failure/parse error with a stricter instruction prefix
            if _is_failed_outputs(outputs):
                add_event("Retrying LLM once due to invalid/parse-error output")
                context_retry_payload = OrderedDict([
                    ("retry_instruction", "Return ONLY the JSON array per schema with no prose."),
                    ("original_context", context_payload)
                ])
                context_retry = json.dumps(context_retry_payload, default=json_default)
                try:
                    outputs = agent.get_decisions(
                        context=context_retry, 
                        assets=runtime_config["assets"],
                        config=runtime_config, 
                        account_data=account
                    )
                    if not isinstance(outputs, dict):
                        add_event(f"Retry invalid format: {outputs}")
                        outputs = {}
                except Exception as e:
                    import traceback
                    add_event(f"Retry agent error: {e}")
                    add_event(f"Retry traceback: {traceback.format_exc()}")
                    outputs = {}

            reasoning_text = outputs.get("reasoning", "") if isinstance(outputs, dict) else ""
            if reasoning_text:
                add_event(f"LLM reasoning summary: {reasoning_text}")

            # Execute trades for each asset
            for output in outputs.get("trade_decisions", []) if isinstance(outputs, dict) else []:
                try:
                    asset = output.get("asset")
                    if not asset or asset not in runtime_config["assets"]:
                        continue
                    action = output.get("action")
                    current_price = asset_prices.get(asset, 0)
                    action = output["action"]
                    rationale = output.get("rationale", "")
                    if rationale:
                        add_event(f"Decision rationale for {asset}: {rationale}")
                    if action in ("buy", "sell"):
                        is_buy = action == "buy"
                        alloc_usd = float(output.get("allocation_usd", 0.0))
                        if alloc_usd <= 0:
                            add_event(f"Holding {asset}: zero/negative allocation")
                            continue
                        amount = alloc_usd / current_price

                        order = await hyperliquid.place_buy_order(asset, amount) if is_buy else await hyperliquid.place_sell_order(asset, amount)
                        # Confirm by checking recent fills for this asset shortly after placing
                        await asyncio.sleep(1)
                        fills_check = await hyperliquid.get_recent_fills(limit=10)
                        filled = False
                        for fc in reversed(fills_check):
                            try:
                                if (fc.get('coin') == asset or fc.get('asset') == asset):
                                    filled = True
                                    break
                            except Exception:
                                continue
                        trade_log.append({"type": action, "price": current_price, "amount": amount, "exit_plan": output["exit_plan"], "filled": filled})
                        tp_oid = None
                        sl_oid = None
                        if output["tp_price"]:
                            tp_order = await hyperliquid.place_take_profit(asset, is_buy, amount, output["tp_price"])
                            tp_oids = hyperliquid.extract_oids(tp_order)
                            tp_oid = tp_oids[0] if tp_oids else None
                            add_event(f"TP placed {asset} at {output['tp_price']}")
                        if output["sl_price"]:
                            sl_order = await hyperliquid.place_stop_loss(asset, is_buy, amount, output["sl_price"])
                            sl_oids = hyperliquid.extract_oids(sl_order)
                            sl_oid = sl_oids[0] if sl_oids else None
                            add_event(f"SL placed {asset} at {output['sl_price']}")
                        # Reconcile: if opposite-side position exists or TP/SL just filled, clear stale active_trades for this asset
                        for existing in active_trades[:]:
                            if existing.get('asset') == asset:
                                try:
                                    active_trades.remove(existing)
                                except ValueError:
                                    pass
                        active_trades.append({
                            "asset": asset,
                            "is_long": is_buy,
                            "amount": amount,
                            "entry_price": current_price,
                            "tp_oid": tp_oid,
                            "sl_oid": sl_oid,
                            "exit_plan": output["exit_plan"],
                            "opened_at": datetime.now().isoformat()
                        })
                        add_event(f"{action.upper()} {asset} amount {amount:.4f} at ~{current_price}")
                        if rationale:
                            add_event(f"Post-trade rationale for {asset}: {rationale}")
                        # Write to diary after confirming fills status
                        with open(diary_path, "a") as f:
                            diary_entry = {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "asset": asset,
                                "action": action,
                                "allocation_usd": alloc_usd,
                                "amount": amount,
                                "entry_price": current_price,
                                "tp_price": output.get("tp_price"),
                                "tp_oid": tp_oid,
                                "sl_price": output.get("sl_price"),
                                "sl_oid": sl_oid,
                                "exit_plan": output.get("exit_plan", ""),
                                "rationale": output.get("rationale", ""),
                                "order_result": str(order),
                                "opened_at": datetime.now(timezone.utc).isoformat(),
                                "filled": filled
                            }
                            f.write(json.dumps(diary_entry) + "\n")
                    else:
                        add_event(f"Hold {asset}: {output.get('rationale', '')}")
                        # Write hold to diary
                        with open(diary_path, "a") as f:
                            diary_entry = {
                                "timestamp": datetime.now().isoformat(),
                                "asset": asset,
                                "action": "hold",
                                "rationale": output.get("rationale", "")
                            }
                            f.write(json.dumps(diary_entry) + "\n")
                except Exception as e:
                    import traceback
                    add_event(f"Execution error {asset}: {e}")

            next_run_timestamp = (datetime.now(timezone.utc).timestamp() + interval_seconds) * 1000
            # Determine sleep duration but allow interruption if config changes
            current_interval_seconds = interval_seconds
            for i in range(current_interval_seconds):
                # Always update next_run_timestamp (even when paused) so dashboard shows accurate countdown
                next_run_timestamp = (datetime.now(timezone.utc).timestamp() + (current_interval_seconds - i)) * 1000
                
                # Always check if interval config changed dynamically
                new_interval_val = get_interval_seconds(runtime_config["interval"])
                if i % 10 == 0:
                     logging.info(f"Sleep loop {i}/{current_interval_seconds}. Current: {current_interval_seconds}, New: {new_interval_val}, Paused: {bot_paused}")
                if new_interval_val != current_interval_seconds:
                    add_event(f"🔄 Interval changed detected ({current_interval_seconds}s -> {new_interval_val}s). Restarting loop.")
                    interval_seconds = new_interval_val
                    current_interval_seconds = new_interval_val  # Reset the loop target
                    break
                
                await asyncio.sleep(1)
            # Recalculate interval in case it changed
            interval_seconds = get_interval_seconds(runtime_config["interval"])

    async def handle_diary(request):
        """Return diary entries as JSON or newline-delimited text."""
        try:
            raw = request.query.get('raw')
            download = request.query.get('download')
            if raw or download:
                if not os.path.exists(diary_path):
                    return web.Response(text="", content_type="text/plain")
                with open(diary_path, "r") as f:
                    data = f.read()
                headers = {}
                if download:
                    headers["Content-Disposition"] = f"attachment; filename=diary.jsonl"
                return web.Response(text=data, content_type="text/plain", headers=headers)
            limit = int(request.query.get('limit', '200'))
            with open(diary_path, "r") as f:
                lines = f.readlines()
            start = max(0, len(lines) - limit)
            entries = [json.loads(l) for l in lines[start:]]
            return web.json_response({"entries": entries})
        except FileNotFoundError:
            return web.json_response({"entries": []})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_logs(request):
        """Stream log files with optional download or tailing behaviour."""
        try:
            path = request.query.get('path', 'llm_requests.log')
            download = request.query.get('download')
            limit_param = request.query.get('limit')
            if not os.path.exists(path):
                return web.Response(text="", content_type="text/plain")
            with open(path, "r") as f:
                data = f.read()
            if download or (limit_param and (limit_param.lower() == 'all' or limit_param == '-1')):
                headers = {}
                if download:
                    headers["Content-Disposition"] = f"attachment; filename={os.path.basename(path)}"
                return web.Response(text=data, content_type="text/plain", headers=headers)
            limit = int(limit_param) if limit_param else 2000
            return web.Response(text=data[-limit:], content_type="text/plain")
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_dashboard(request):
        """Serve the dashboard HTML file."""
        try:
            dashboard_path = os.path.join(os.path.dirname(__file__), "..", "dashboard.html")
            with open(dashboard_path, "r", encoding="utf-8") as f:
                content = f.read()
            return web.Response(text=content, content_type="text/html")
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_account(request):
        """Return current account state."""
        try:
            state = await hyperliquid.get_user_state()
            return web.json_response(state)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_positions(request):
        """Return current open positions with SL/TP levels."""
        try:
            state = await hyperliquid.get_user_state()
            positions = state.get('positions', [])
            open_orders = await hyperliquid.get_open_orders()
            
            # Enrich with current prices and SL/TP
            for pos in positions:
                coin = pos.get('coin')
                try:
                    if coin:
                        current_price = await hyperliquid.get_current_price(coin)
                        pos['current_price'] = current_price
                        
                        # Find SL/TP orders for this coin
                        pos['sl'] = None
                        pos['tp'] = None
                        for order in open_orders:
                            if order.get('coin') == coin:
                                o_type = order.get('orderType', '').upper()
                                trigger_px = order.get('triggerPx')
                                if 'STOP' in o_type:
                                    pos['sl'] = trigger_px
                                elif 'TAKE_PROFIT' in o_type:
                                    pos['tp'] = trigger_px
                except Exception:
                    pos['current_price'] = pos.get('current_price', 0)
            
            return web.json_response(positions)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_close_position(request):
        """Close a specific position."""
        try:
            asset = request.match_info.get('asset')
            data = await request.json()
            close_type = data.get('type', 'market')
            
            # Get current position
            state = await hyperliquid.get_user_state()
            # Match by exact symbol (BTCUSDT) or by base asset (BTC)
            position = next((p for p in state['positions'] if p.get('coin') == asset or p.get('coin') == f"{asset}USDT"), None)
            
            if not position:
                add_event(f"Position not found for {asset}")
                return web.json_response({"error": "Position not found"}, status=404)
            
            symbol = position.get('coin')  # Use the actual symbol from Binance
            size = abs(float(position.get('szi', 0)))
            is_long = float(position.get('szi', 0)) > 0
            
            add_event(f"Closing position: {symbol}, size={size}, is_long={is_long}")
            
            # Round quantity to proper precision
            quantity = hyperliquid.round_quantity(symbol, size)
            
            # Close the position directly with Binance API
            if is_long:
                result = await hyperliquid._retry(
                    hyperliquid.client.futures_create_order,
                    symbol=symbol,
                    side="SELL",
                    type="MARKET",
                    quantity=quantity
                )
            else:
                result = await hyperliquid._retry(
                    hyperliquid.client.futures_create_order,
                    symbol=symbol,
                    side="BUY",
                    type="MARKET",
                    quantity=quantity
                )
            
            add_event(f"Position closed: {symbol}, orderId: {result.get('orderId', 'unknown')}")
            
            return web.json_response({"status": "success", "result": str(result)})
        except Exception as e:
            add_event(f"Error closing position: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_close_all_positions(request):
        """Close all open positions."""
        try:
            state = await hyperliquid.get_user_state()
            positions = state.get('positions', [])
            
            results = []
            closed_count = 0
            for pos in positions:
                try:
                    # coin is already in BTCUSDT format from Binance
                    symbol = pos.get('coin')
                    size = abs(float(pos.get('szi', 0)))
                    
                    # Skip positions with no size
                    if size == 0 or size < 0.0001:
                        continue
                        
                    is_long = float(pos.get('szi', 0)) > 0
                    
                    add_event(f"Closing position: {symbol}, size={size}, is_long={is_long}")
                    
                    # Round quantity to proper precision
                    quantity = hyperliquid.round_quantity(symbol, size)
                    
                    # Place order directly with the symbol (already in BTCUSDT format)
                    if is_long:
                        # Close long = sell
                        result = await hyperliquid._retry(
                            hyperliquid.client.futures_create_order,
                            symbol=symbol,
                            side="SELL",
                            type="MARKET",
                            quantity=quantity
                        )
                    else:
                        # Close short = buy
                        result = await hyperliquid._retry(
                            hyperliquid.client.futures_create_order,
                            symbol=symbol,
                            side="BUY",
                            type="MARKET",
                            quantity=quantity
                        )
                    
                    add_event(f"Position closed: {symbol}, result: {result.get('orderId', 'unknown')}")
                    results.append({"asset": symbol, "status": "closed", "size": size})
                    closed_count += 1
                except Exception as e:
                    add_event(f"Error closing {symbol}: {e}")
                    results.append({"asset": symbol, "status": "error", "error": str(e)})
            
            if closed_count == 0:
                add_event("No open positions to close")
                return web.json_response({"status": "no_positions", "message": "No hay posiciones abiertas para cerrar", "results": []})
            
            add_event(f"Closed {closed_count} positions via dashboard")
            
            return web.json_response({"status": "success", "closed_count": closed_count, "results": results})
        except Exception as e:
            add_event(f"Error in close_all_positions: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def handle_bot_start(request):
        """Start/resume the bot."""
        nonlocal bot_paused
        bot_paused = False
        add_event("Bot started via dashboard")
        return web.json_response({"status": "running"})

    async def handle_bot_stop(request):
        """Pause the bot."""
        nonlocal bot_paused
        bot_paused = True
        add_event("Bot paused via dashboard")
        return web.json_response({"status": "paused"})

    async def handle_bot_status(request):
        """Get bot status."""
        return web.json_response({
            "status": "paused" if bot_paused else "running",
            "uptime": (datetime.now(timezone.utc) - start_time).total_seconds(),
            "invocation_count": invocation_count,
            "next_run": next_run_timestamp
        })

    async def handle_prompt_logs(request):
        """Return the latest entries from prompts.log."""
        try:
            path = "prompts.log"
            if not os.path.exists(path):
                return web.Response(text="No prompt logs yet.", content_type="text/plain")
            
            # Read last 5000 chars
            with open(path, "r", encoding="utf-8") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 10000), os.SEEK_SET)
                data = f.read()
            
            return web.Response(text=data, content_type="text/plain")
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_get_config(request):
        """Return current runtime configuration."""
        return web.json_response({
            "assets": runtime_config["assets"],
            "interval": runtime_config["interval"],
            "leverage": runtime_config.get("leverage", 20),
            "risk_config": runtime_config.get("risk_config", {}),
            "llm_model": runtime_config.get("llm_model", agent.model),
            "available_assets": AVAILABLE_ASSETS,
            "available_intervals": AVAILABLE_INTERVALS,
            "available_leverages": AVAILABLE_LEVERAGES
        })

    async def handle_set_config(request):
        """Update runtime configuration (assets and/or interval)."""
        try:
            data = await request.json()
            updated = []
            if "assets" in data and isinstance(data["assets"], list) and len(data["assets"]) > 0:
                # Validate assets
                valid_assets = [a for a in data["assets"] if a in AVAILABLE_ASSETS]
                if valid_assets:
                    runtime_config["assets"] = valid_assets
                    updated.append("assets")
                    add_event(f"Config updated: assets = {valid_assets}")
            if "interval" in data and data["interval"] in AVAILABLE_INTERVALS:
                runtime_config["interval"] = data["interval"]
                updated.append("interval")
                add_event(f"Config updated: interval = {data['interval']}")
            
            if "leverage" in data:
                try:
                    new_lev = int(data["leverage"])
                    if new_lev in AVAILABLE_LEVERAGES:
                        runtime_config["leverage"] = new_lev
                        updated.append("leverage")
                        add_event(f"Config updated: leverage = {new_lev}x")
                        
                        # Apply leverage to all active assets
                        for asset in runtime_config["assets"]:
                            try:
                                await hyperliquid.set_leverage(asset, new_lev)
                                add_event(f"Applied {new_lev}x leverage to {asset}")
                            except Exception as e:
                                add_event(f"Failed to set leverage for {asset}: {e}")
                except ValueError:
                    pass
            
            if "risk_config" in data:
                runtime_config["risk_config"] = data["risk_config"]
                updated.append("risk_config")
                add_event(f"Risk config updated: {data['risk_config']}")
            
            if "llm_model" in data and data["llm_model"]:
                new_model = data["llm_model"]
                runtime_config["llm_model"] = new_model
                agent.model = new_model  # Update agent's model
                updated.append("llm_model")
                add_event(f"LLM model changed to: {new_model}")

            if updated:
                save_runtime_config_file(runtime_config)

            return web.json_response({
                "status": "updated" if updated else "no_changes",
                "updated_fields": updated,
                "config": runtime_config
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_get_prompts(request):
        """Get current system prompt and history."""
        return web.json_response({
            "current": prompt_manager.get_current_prompt(),
            "history": prompt_manager.get_history()
        })

    async def handle_update_prompt(request):
        """Update system prompt."""
        try:
            data = await request.json()
            content = data.get("content")
            if not content:
                return web.json_response({"error": "Content required"}, status=400)
            
            updated = prompt_manager.update_prompt(content)
            if updated:
                agent.set_system_prompt(content)
                add_event("System prompt updated via dashboard")
            return web.json_response({"status": "updated" if updated else "no_change"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_restore_prompt(request):
        """Restore system prompt from history."""
        try:
            data = await request.json()
            prompt_id = data.get("id")
            if not prompt_id:
                return web.json_response({"error": "ID required"}, status=400)
                
            success = prompt_manager.restore_from_history(prompt_id)
            if success:
                agent.set_system_prompt(prompt_manager.get_current_prompt())
                add_event(f"System prompt restored (ID: {prompt_id})")
                return web.json_response({"status": "restored"})
            return web.json_response({"error": "Prompt not found"}, status=404)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_save_prompt_as(request):
        """Save prompt as a named version."""
        try:
            data = await request.json()
            content = data.get("content")
            name = data.get("name")
            if not content or not name:
                return web.json_response({"error": "Content and name required"}, status=400)
            
            prompt_manager.save_named_version(content, name)
            # Update agent too
            agent.set_system_prompt(content)
            add_event(f"System prompt saved as '{name}'")
            return web.json_response({"status": "saved"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_trade_history(request):
        """Return trade history for dashboard display."""
        try:
            limit = int(request.query.get('limit', '50'))
            history = get_trade_history(diary_path, limit)
            perf = calculate_performance(diary_path)
            return web.json_response({
                "trades": history,
                "performance": perf
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_data_health(request):
        """Return current data quality status per asset."""
        return web.json_response(current_data_quality)

    async def start_api(app):
        """Register HTTP endpoints for observing diary entries and logs."""
        # Original endpoints
        app.router.add_get('/diary', handle_diary)
        app.router.add_get('/logs', handle_logs)
        app.router.add_get('/api/logs/prompts', handle_prompt_logs)
        
        # Dashboard endpoints
        app.router.add_get('/', handle_dashboard)
        app.router.add_get('/dashboard', handle_dashboard)
        app.router.add_get('/api/account', handle_account)
        app.router.add_get('/api/positions', handle_positions)
        app.router.add_post('/api/position/{asset}/close', handle_close_position)
        app.router.add_post('/api/positions/close-all', handle_close_all_positions)
        app.router.add_post('/api/bot/start', handle_bot_start)
        app.router.add_post('/api/bot/stop', handle_bot_stop)
        app.router.add_get('/api/bot/status', handle_bot_status)
        
        # Config endpoints
        app.router.add_get('/api/config', handle_get_config)
        app.router.add_post('/api/config', handle_set_config)
        
        # Prompt Editor endpoints
        app.router.add_get('/api/prompts', handle_get_prompts)
        app.router.add_post('/api/prompts', handle_update_prompt)
        app.router.add_post('/api/prompts/restore', handle_restore_prompt)
        app.router.add_post('/api/prompts/save_as', handle_save_prompt_as)
        
        # Trade History endpoint
        app.router.add_get('/api/trade-history', handle_trade_history)
        
        # Data Health endpoint
        app.router.add_get('/api/data-health', handle_data_health)

    async def main_async():
        """Start the aiohttp server and kick off the trading loop."""
        app = web.Application()
        await start_api(app)
        from src.config_loader import CONFIG as CFG
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, CFG.get("api_host"), int(CFG.get("api_port")))
        await site.start()
        await run_loop()

    def calculate_total_return(state, trade_log):
        """Compute percent return relative to an assumed initial balance."""
        initial = 10000
        current = state['balance'] + sum(p.get('pnl', 0) for p in state.get('positions', []))
        return ((current - initial) / initial) * 100 if initial else 0

    def calculate_sharpe(returns):
        """Compute a naive Sharpe-like ratio from the trade log."""
        if not returns:
            return 0
        vals = [r.get('pnl', 0) if 'pnl' in r else 0 for r in returns]
        if not vals:
            return 0
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        std = math.sqrt(var) if var > 0 else 0
        return mean / std if std > 0 else 0

    async def check_exit_condition(trade, taapi, hyperliquid):
        """Evaluate whether a given trade's exit plan triggers a close."""
        plan = (trade.get("exit_plan") or "").lower()
        if not plan:
            return False
        try:
            if "macd" in plan and "below" in plan:
                macd = taapi.get_indicators(trade["asset"], "4h")["macd"]["valueMACD"]
                threshold = float(plan.split("below")[-1].strip())
                return macd < threshold
            if "close above ema50" in plan:
                symbol = normalize_symbol(trade['asset'])
                ema50 = taapi.get_historical_indicator("ema", symbol, "4h", results=1, params={"period": 50})[0]["value"]
                current = await hyperliquid.get_current_price(trade["asset"])
                return current > ema50
        except Exception:
            return False
        return False

    asyncio.run(main_async())


if __name__ == "__main__":
    main()
