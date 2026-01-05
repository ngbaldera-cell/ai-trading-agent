"""Decision-making agent that orchestrates LLM prompts and indicator lookups."""

import requests
from src.config_loader import CONFIG
from src.indicators.taapi_client import TAAPIClient
import json
import logging
from datetime import datetime

class TradingAgent:
    """High-level trading agent that delegates reasoning to an LLM service."""

    def __init__(self):
        """Initialize LLM configuration, metadata headers, and indicator helper."""
        self.model = CONFIG["llm_model"]
        self.api_key = CONFIG["openrouter_api_key"]
        base = CONFIG["openrouter_base_url"]
        self.base_url = f"{base}/chat/completions"
        self.referer = CONFIG.get("openrouter_referer")
        self.app_title = CONFIG.get("openrouter_app_title")
        self.taapi = TAAPIClient()
        # Fast/cheap sanitizer model to normalize outputs on parse failures
        self.sanitize_model = CONFIG.get("sanitize_model") or "openai/gpt-5"
        
        # Default system prompt template (will be overridden by PromptManager)
        self.system_prompt_template = None

    def set_system_prompt(self, template: str):
        """Update the system prompt template."""
        self.system_prompt_template = template

    def get_decisions(self, context, assets, config=None, account_data=None):
        """
        Get trade decisions for the current context.
        
        Args:
            context (str/dict): The context payload describing market and account state.
            assets (list[str]): List of assets to trade.
            config (dict, optional): Runtime configuration for prompt variable injection.
            account_data (dict, optional): Account data for calculating limits (e.g. max pos size USD).

        Returns:
            List of trade decision payloads, one per asset.
        """
        return self._decide(context, assets, config, account_data)

    def _decide(self, context, assets, config=None, account_data=None):
        """Dispatch decision request to the LLM and enforce output contract."""
        # Use dynamic system prompt if available, otherwise fallback (though should be set)
        if self.system_prompt_template:
            system_prompt = self.system_prompt_template.replace("{{ASSETS}}", json.dumps(assets))
            
            # Inject dynamic variables if config provided
            if config:
                # Basic Config
                system_prompt = system_prompt.replace("{{LEVERAGE}}", str(config.get("leverage", 20)))
                system_prompt = system_prompt.replace("{{TIMEFRAME}}", str(config.get("interval", "5m")))
                
                # Risk Config
                rc = config.get("risk_config", {})
                if rc:
                    system_prompt = system_prompt.replace("{{RISK_PER_TRADE}}", str(rc.get("risk_per_trade", 1.0)))
                    system_prompt = system_prompt.replace("{{MAX_DAILY_LOSS}}", str(rc.get("max_daily_loss", 3.0)))
                    system_prompt = system_prompt.replace("{{MAX_TRADES_PER_DAY}}", str(rc.get("max_simultaneous_trades", 2)))
                    
                    # Calculate Max Position Size in USD
                    max_pos_pct = rc.get("max_position_size_pct", 10.0)
                    if account_data and "margin_balance" in account_data:
                        try:
                            equity = float(account_data["margin_balance"])
                            max_pos_usd = round(equity * (max_pos_pct / 100.0), 2)
                            system_prompt = system_prompt.replace("{{MAX_POSITION_SIZE}}", str(max_pos_usd))
                        except (ValueError, TypeError):
                            system_prompt = system_prompt.replace("{{MAX_POSITION_SIZE}}", f"{max_pos_pct}% of equity")
                    else:
                        system_prompt = system_prompt.replace("{{MAX_POSITION_SIZE}}", f"{max_pos_pct}% of equity")
                        
        else:
            # Fallback to a minimal safe prompt if not set (should not happen with PromptManager)
            logging.warning("System prompt template not set! Using minimal fallback.")
            system_prompt = (
                f"QUANTITATIVE TRADER optimizing perpetual futures returns.\n"
                f"Assets: {json.dumps(assets)}\n"
                "Output JSON: {reasoning, trade_decisions}."
            )

        user_prompt = context
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        tools = [{
            "type": "function",
            "function": {
                "name": "fetch_taapi_indicator",
                "description": ("Fetch any TAAPI indicator. Available: ema, sma, rsi, macd, bbands, stochastic, stochrsi, "
                    "adx, atr, cci, dmi, ichimoku, supertrend, vwap, obv, mfi, willr, roc, mom, sar (parabolic), "
                    "fibonacci, pivotpoints, keltner, donchian, awesome, gator, alligator, and 200+ more. "
                    "See https://taapi.io/indicators/ for full list and parameters."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "indicator": {"type": "string"},
                        "symbol": {"type": "string"},
                        "interval": {"type": "string"},
                        "period": {"type": "integer"},
                        "backtrack": {"type": "integer"},
                        "other_params": {"type": "object", "additionalProperties": {"type": ["string", "number", "boolean"]}},
                    },
                    "required": ["indicator", "symbol", "interval"],
                    "additionalProperties": False,
                },
            },
        }]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        if self.app_title:
            headers["X-Title"] = self.app_title

        def _post(payload):
            """Send a POST request to OpenRouter, logging request and response metadata."""
            # Log the full request payload for debugging
            logging.info("Sending request to OpenRouter (model: %s)", payload.get('model'))
            with open("llm_requests.log", "a", encoding="utf-8") as f:
                f.write(f"\n\n=== {datetime.now()} ===\n")
                f.write(f"Model: {payload.get('model')}\n")
                f.write(f"Headers: {json.dumps({k: v for k, v in headers.items() if k != 'Authorization'})}\n")
                f.write(f"Payload:\n{json.dumps(payload, indent=2)}\n")
            resp = requests.post(self.base_url, headers=headers, json=payload, timeout=60)
            logging.info("Received response from OpenRouter (status: %s)", resp.status_code)
            if resp.status_code != 200:
                logging.error("OpenRouter error: %s - %s", resp.status_code, resp.text)
                with open("llm_requests.log", "a", encoding="utf-8") as f:
                    f.write(f"ERROR Response: {resp.status_code} - {resp.text}\n")
            resp.raise_for_status()
            return resp.json()

        def _sanitize_output(raw_content: str, assets_list):
            """Coerce arbitrary LLM output into the required reasoning + decisions schema."""
            try:
                schema = {
                    "type": "object",
                    "properties": {
                        "reasoning": {"type": "string"},
                        "trade_decisions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "asset": {"type": "string", "enum": assets_list},
                                    "action": {"type": "string", "enum": ["buy", "sell", "hold"]},
                                    "allocation_usd": {"type": "number"},
                                    "tp_price": {"type": ["number", "null"]},
                                    "sl_price": {"type": ["number", "null"]},
                                    "exit_plan": {"type": "string"},
                                    "rationale": {"type": "string"},
                                },
                                "required": ["asset", "action", "allocation_usd", "tp_price", "sl_price", "exit_plan", "rationale"],
                                "additionalProperties": False,
                            },
                            "minItems": 1,
                        }
                    },
                    "required": ["reasoning", "trade_decisions"],
                    "additionalProperties": False,
                }
                payload = {
                    "model": self.sanitize_model,
                    "messages": [
                        {"role": "system", "content": (
                            "You are a strict JSON normalizer. Return ONLY a JSON array matching the provided JSON Schema. "
                            "If input is wrapped or has prose/markdown, fix it. Do not add fields."
                        )},
                        {"role": "user", "content": raw_content},
                    ],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "trade_decisions",
                            "strict": True,
                            "schema": schema,
                        },
                    },
                    "temperature": 0,
                }
                resp = _post(payload)
                msg = resp.get("choices", [{}])[0].get("message", {})
                parsed = msg.get("parsed")
                if isinstance(parsed, dict):
                    if "trade_decisions" in parsed:
                        return parsed
                # fallback: try content
                content = msg.get("content") or "[]"
                try:
                    loaded = json.loads(content)
                    if isinstance(loaded, dict) and "trade_decisions" in loaded:
                        return loaded
                except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                    pass
                return {"reasoning": "", "trade_decisions": []}
            except (requests.RequestException, json.JSONDecodeError, KeyError, ValueError, TypeError) as se:
                logging.error("Sanitize failed: %s", se)
                return {"reasoning": "", "trade_decisions": []}

        allow_tools = True
        allow_structured = True

        def _build_schema():
            """Assemble the JSON schema used for structured LLM responses."""
            base_properties = {
                "asset": {"type": "string", "enum": assets},
                "action": {"type": "string", "enum": ["buy", "sell", "hold"]},
                "allocation_usd": {"type": "number", "minimum": 0},
                "tp_price": {"type": ["number", "null"]},
                "sl_price": {"type": ["number", "null"]},
                "exit_plan": {"type": "string"},
                "rationale": {"type": "string"},
            }
            required_keys = ["asset", "action", "allocation_usd", "tp_price", "sl_price", "exit_plan", "rationale"]
            return {
                "type": "object",
                "properties": {
                    "reasoning": {"type": "string"},
                    "trade_decisions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": base_properties,
                            "required": required_keys,
                            "additionalProperties": False,
                        },
                        "minItems": 1,
                    }
                },
                "required": ["reasoning", "trade_decisions"],
                "additionalProperties": False,
            }

        for _ in range(6):
            data = {"model": self.model, "messages": messages, "max_tokens": 4000}  # Limit max_tokens to reduce cost
            if allow_structured:
                data["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "trade_decisions",
                        "strict": True,
                        "schema": _build_schema(),
                    },
                }
            if allow_tools:
                data["tools"] = tools
                data["tool_choice"] = "auto"
            if CONFIG.get("reasoning_enabled"):
                data["reasoning"] = {
                    "enabled": True,
                    "effort": CONFIG.get("reasoning_effort") or "high",
                    # "max_tokens": CONFIG.get("reasoning_max_tokens") or 100000,
                    "exclude": False,
                }
            if CONFIG.get("provider_config") or CONFIG.get("provider_quantizations"):
                provider_payload = dict(CONFIG.get("provider_config") or {})
                quantizations = CONFIG.get("provider_quantizations")
                if quantizations:
                    provider_payload["quantizations"] = quantizations
                data["provider"] = provider_payload
            try:
                resp_json = _post(data)
            except requests.HTTPError as e:
                try:
                    err = e.response.json()
                except (json.JSONDecodeError, ValueError, AttributeError):
                    err = {}
                raw = (err.get("error", {}).get("metadata", {}) or {}).get("raw", "")
                provider = (err.get("error", {}).get("metadata", {}) or {}).get("provider_name", "")
                if e.response.status_code == 422 and provider.lower().startswith("xai") and "deserialize" in raw.lower():
                    logging.warning("xAI rejected tool schema; retrying without tools.")
                    if allow_tools:
                        allow_tools = False
                        continue
                # Provider may not support structured outputs / response_format
                err_text = json.dumps(err)
                if allow_structured and ("response_format" in err_text or "structured" in err_text or e.response.status_code in (400, 422)):
                    logging.warning("Provider rejected structured outputs; retrying without response_format.")
                    allow_structured = False
                    continue
                raise

            choice = resp_json["choices"][0]
            message = choice["message"]
            messages.append(message)
            
            # Log reasoning/thinking if present (from OpenRouter extended thinking)
            reasoning_content = message.get("reasoning_content") or message.get("reasoning") or ""
            if reasoning_content:
                with open("prompts.log", "a", encoding="utf-8") as f:
                    f.write(f"\n\n=== LLM REASONING {datetime.now()} ===\n{reasoning_content}\n")

            tool_calls = message.get("tool_calls") or []
            if allow_tools and tool_calls:
                for tc in tool_calls:
                    if tc.get("type") == "function" and tc.get("function", {}).get("name") == "fetch_taapi_indicator":
                        args = json.loads(tc["function"].get("arguments") or "{}")
                        try:
                            params = {
                                "secret": self.taapi.api_key,
                                "exchange": "binance",
                                "symbol": args["symbol"],
                                "interval": args["interval"],
                            }
                            if args.get("period") is not None:
                                params["period"] = args["period"]
                            if args.get("backtrack") is not None:
                                params["backtrack"] = args["backtrack"]
                            if isinstance(args.get("other_params"), dict):
                                params.update(args["other_params"])
                            ind_resp = requests.get(f"{self.taapi.base_url}{args['indicator']}", params=params, timeout=30).json()
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.get("id"),
                                "name": "fetch_taapi_indicator",
                                "content": json.dumps(ind_resp),
                            })
                        except (requests.RequestException, json.JSONDecodeError, KeyError, ValueError) as ex:
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.get("id"),
                                "name": "fetch_taapi_indicator",
                                "content": f"Error: {str(ex)}",
                            })
                continue

            try:
                # Prefer parsed field from structured outputs if present
                if isinstance(message.get("parsed"), dict):
                    parsed = message.get("parsed")
                else:
                    content = message.get("content") or "{}"
                    # Log raw LLM response for debugging/monitoring
                    with open("prompts.log", "a", encoding="utf-8") as f:
                        f.write(f"\n\n=== LLM RESPONSE {datetime.now()} ===\n{content}\n")
                    parsed = json.loads(content)

                if not isinstance(parsed, dict):
                    logging.error("Expected dict payload, got: %s; attempting sanitize", type(parsed))
                    sanitized = _sanitize_output(content if 'content' in locals() else json.dumps(parsed), assets)
                    if sanitized.get("trade_decisions"):
                        return sanitized
                    return {"reasoning": "", "trade_decisions": []}

                reasoning_text = parsed.get("reasoning", "") or ""
                decisions = parsed.get("trade_decisions")

                if isinstance(decisions, list):
                    normalized = []
                    for item in decisions:
                        if isinstance(item, dict):
                            item.setdefault("allocation_usd", 0.0)
                            item.setdefault("tp_price", None)
                            item.setdefault("sl_price", None)
                            item.setdefault("exit_plan", "")
                            item.setdefault("rationale", "")
                            normalized.append(item)
                        elif isinstance(item, list) and len(item) >= 7:
                            normalized.append({
                                "asset": item[0],
                                "action": item[1],
                                "allocation_usd": float(item[2]) if item[2] else 0.0,
                                "tp_price": float(item[3]) if item[3] and item[3] != "null" else None,
                                "sl_price": float(item[4]) if item[4] and item[4] != "null" else None,
                                "exit_plan": item[5] if len(item) > 5 else "",
                                "rationale": item[6] if len(item) > 6 else ""
                            })
                    return {"reasoning": reasoning_text, "trade_decisions": normalized}

                logging.error("trade_decisions missing or invalid; attempting sanitize")
                sanitized = _sanitize_output(content if 'content' in locals() else json.dumps(parsed), assets)
                if sanitized.get("trade_decisions"):
                    return sanitized
                return {"reasoning": reasoning_text, "trade_decisions": []}
            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                logging.error("JSON parse error: %s, content: %s", e, content[:200])
                # Try sanitizer as last resort
                sanitized = _sanitize_output(content, assets)
                if sanitized.get("trade_decisions"):
                    return sanitized
                return {
                    "reasoning": "Parse error",
                    "trade_decisions": [{
                        "asset": a,
                        "action": "hold",
                        "allocation_usd": 0.0,
                        "tp_price": None,
                        "sl_price": None,
                        "exit_plan": "",
                        "rationale": "Parse error"
                    } for a in assets]
                }

        return {
            "reasoning": "tool loop cap",
            "trade_decisions": [{
                "asset": a,
                "action": "hold",
                "allocation_usd": 0.0,
                "tp_price": None,
                "sl_price": None,
                "exit_plan": "",
                "rationale": "tool loop cap"
            } for a in assets]
        }
