# Guía de Ingeniería de Prompts para la Arquitectura "AntiGravity"

Esta arquitectura está diseñada como un sistema **Híbrido Determinista-Generativo**. El código Python gestiona la "mecánica" (ejecución, riesgo duro, datos), mientras que el LLM gestiona la "táctica" (análisis, decisión).

Para maximizar la sinergia, tus prompts deben hablar el "lenguaje" de las variables inyectadas y respetar el contrato de salida JSON.

---

## 1. Variables Dinámicas (El "Puente")
El sistema inyecta datos en tiempo real antes de enviar el prompt a la IA. Usa estos placeholders para que tu prompt se adapte automáticamente a la configuración del dashboard.

| Placeholder | Descripción | Uso Recomendado en Prompt |
| :--- | :--- | :--- |
| `{{ASSETS}}` | Lista de activos activos (ej. `["BTC", "ETH"]`). | "Analiza los siguientes activos: {{ASSETS}}..." |
| `{{LEVERAGE}}` | Apalancamiento configurado (ej. `20`). | "Nunca excedas {{LEVERAGE}}x de apalancamiento efectivo." |
| `{{TIMEFRAME}}` | Intervalo temporal (ej. `5m`, `1h`). | "Prioriza la tendencia en {{TIMEFRAME}} para entradas." |
| `{{RISK_PER_TRADE}}` | % Riesgo por operación (ej. `1.0`). | "Calcula el tamaño de posición tal que el riesgo sea ≤ {{RISK_PER_TRADE}}%." |
| `{{MAX_DAILY_LOSS}}` | % Pérdida diaria máxima. | "Si la pérdida diaria > {{MAX_DAILY_LOSS}}%, sugiere acción 'hold' forzosa." |
| `{{MAX_POSITION_SIZE}}` | Límite de tamaño (USD o %). | "Cap allocation_usd to {{MAX_POSITION_SIZE}}." |
| `{{MAX_TRADES_PER_DAY}}` | Límite de operaciones simultáneas. | "No abras nuevas posiciones si active_trades >= {{MAX_TRADES_PER_DAY}}." |

### Ejemplo de Bloque de Restricciones
```text
RESTRICCIONES OPERATIVAS (INVIOLABLES):
- Apalancamiento Máximo: {{LEVERAGE}}x
- Riesgo por Trade: {{RISK_PER_TRADE}}% del balance
- Timeframe Principal: {{TIMEFRAME}}
```

---

## 2. Estructura de "Contexto" (Lo que la IA recibe)
En cada ciclo, la IA recibe un JSON gigante (`user_message`) con:
1.  **Account State**: Balance, PnL no realizado, margen usado.
2.  **Market Data**: Precios OHLCV actuales, indicadores técnicos pre-calculados (si los hay).
3.  **Active Trades**: Posiciones abiertas actualmente.
4.  **Trading History**: Operaciones recientes del día.

**Tu prompt debe enseñar a la IA a leer esto:**
> "Recibirás un objeto JSON con el estado del mercado. Primero revisa `active_trades` para gestionar posiciones abiertas antes de buscar nuevas entradas."

---

## 3. Uso de Herramientas (Tool Calling)
La arquitectura expone `fetch_taapi_indicator`. La IA puede "preguntar" por datos extra si no está segura.

**Instrucción Clave:**
> "Si la tendencia no es clara con los datos proporcionados, USA la herramienta `fetch_taapi_indicator` (ej. RSI, MACD, Bandas de Bollinger) para confirmar. NO adivines."

---

## 4. El Contrato de Salida (JSON Output)
El sistema Python espera una respuesta JSON **estricta**. Si el prompt permite prosa libre fuera del JSON, el sistema fallará (o tendrá que reintentar).

**Plantilla Obligatoria al final del Prompt:**
```text
OUTPUT FORMAT (JSON ONLY):
{
  "reasoning": "Explicación detallada paso a paso...",
  "trade_decisions": [
    {
      "asset": "BTC",
      "action": "buy|sell|hold",
      "allocation_usd": <number>,
      "leverage": <number>,
      "tp_price": <number>,
      "sl_price": <number>,
      "exit_plan": "Condiciones para salir...",
      "rationale": "Resumen breve"
    }
  ]
}
```

---

## 5. Arquitectura de Decisión ("Chain of Thought")
Para obtener mejores resultados, fuerza a la IA a pensar en pasos lógicos antes de decidir.

**Ejemplo de Flujo en Prompt:**
1.  **Fase de Diagnóstico**: "Analiza la estructura de mercado (HH/HL) en 4h y {{TIMEFRAME}}."
2.  **Fase de Riesgo**: "Verifica si abrir un trade viola `{{MAX_DAILY_LOSS}}`."
3.  **Fase de Señal**: "Busca confluencia de al menos 3 factores (Precio, Volumen, Indicador)."
4.  **Fase de Ejecución**: "Define TP/SL basados en ATR, no en números mágicos."

---

## 6. Ejemplo de "Meta-Prompt" Optimizado

```text
Eres un Quant Trader AI operando en Binance Futures.
Tu objetivo es maximizar retorno ajustado por riesgo (Sharpe Ratio).

CONFIGURACIÓN DINÁMICA:
- Operas en gráficos de {{TIMEFRAME}}.
- Tienes prohibido arriesgar más del {{RISK_PER_TRADE}}% por operación.
- Tamaño máximo de posición: {{MAX_POSITION_SIZE}}.

REGLAS DE ENGAGEMENT:
1. Analiza la tendencia macro (4h) recibida en el contexto.
2. Si la tendencia macro contradice la señal en {{TIMEFRAME}}, la acción es HOLD.
3. Si el "unrealized_pnl" de la cuenta es negativo, reduce el tamaño de nuevas posiciones a la mitad.

USO DE HERRAMIENTAS:
Si el contexto no incluye RSI o MACD actuales, usa `fetch_taapi_indicator` para obtenerlos antes de decidir.

SALIDA:
Genera EXCLUSIVAMENTE un JSON válido con campos "reasoning" y "trade_decisions".
```
