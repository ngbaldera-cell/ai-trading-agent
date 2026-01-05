# 📊 Guía de Monitoreo del Bot de Trading

## ✅ El Bot Está Funcionando

Si ves este mensaje, ¡tu bot está operativo!:
```
🧪 Binance client initialized in TESTNET mode (paper trading)
🔄 Using Binance exchange
Starting trading agent for assets: ['BTC', 'ETH', 'SOL'] at interval: 5m
```

---

## 🔍 Formas de Monitorear el Bot

### **1️⃣ API Web (RECOMENDADO)**

El bot expone endpoints HTTP en `http://localhost:3000`:

#### **📖 Ver Historial de Decisiones (Diary)**
```
http://localhost:3000/diary
```

**Qué muestra:**
- Todas las decisiones de trading (buy, sell, hold)
- Razones (rationale) de cada decisión
- Precios de entrada, take-profit, stop-loss
- Timestamps de cada acción

**Ejemplo de uso:**
1. Abre tu navegador
2. Ve a: `http://localhost:3000/diary`
3. Verás un JSON con todas las decisiones

**Parámetros útiles:**
- `?limit=50` - Mostrar últimas 50 entradas
- `?raw=true` - Ver formato JSONL crudo
- `?download=true` - Descargar el archivo

#### **📝 Ver Logs del Sistema**
```
http://localhost:3000/logs
```

**Qué muestra:**
- Logs técnicos del bot
- Errores y advertencias
- Conexiones a APIs
- Detalles de ejecución

**Parámetros útiles:**
- `?limit=5000` - Mostrar últimos 5000 caracteres
- `?download=true` - Descargar logs completos

---

### **2️⃣ Archivo diary.jsonl**

El bot guarda todas sus decisiones en:
```
diary.jsonl
```

**Cómo verlo:**
```bash
# Ver últimas 10 líneas
Get-Content diary.jsonl -Tail 10

# Ver todo el archivo
Get-Content diary.jsonl

# Buscar decisiones de BTC
Select-String -Path diary.jsonl -Pattern "BTC"
```

**Formato de cada línea:**
```json
{
  "timestamp": "2025-12-24T12:45:00Z",
  "asset": "BTC",
  "action": "buy",
  "allocation_usd": 100.0,
  "amount": 0.001,
  "entry_price": 95000.0,
  "tp_price": 96000.0,
  "sl_price": 94000.0,
  "rationale": "Strong bullish momentum...",
  "filled": true
}
```

---

### **3️⃣ Terminal / Consola**

Los logs en tiempo real se muestran donde ejecutaste el bot.

**Mensajes importantes a buscar:**

✅ **Conexión exitosa:**
```
🧪 Binance client initialized in TESTNET mode
```

📈 **Orden de compra:**
```
📈 Placing BUY order: 0.001 BTCUSDT
```

📉 **Orden de venta:**
```
📉 Placing SELL order: 0.001 BTCUSDT
```

🎯 **Take Profit colocado:**
```
🎯 Placing TAKE_PROFIT order: SELL 0.001 BTCUSDT @ 96000
```

🛑 **Stop Loss colocado:**
```
🛑 Placing STOP_LOSS order: SELL 0.001 BTCUSDT @ 94000
```

⚠️ **Advertencias comunes:**
```
WARNING - TAAPI fetch_series exception: 429 Too Many Requests
```
(Esto es normal si usas el plan gratuito de TAAPI)

---

### **4️⃣ Binance Testnet Dashboard**

Ve directamente a Binance para ver tus posiciones:

1. Ve a: **https://testnet.binancefuture.com/**
2. Inicia sesión
3. Verás:
   - Balance actual
   - Posiciones abiertas
   - Órdenes activas
   - Historial de trades

---

## 📊 Entendiendo las Decisiones del Bot

### **Tipos de Acciones**

1. **buy** - Abrir posición larga (apuesta a que el precio subirá)
2. **sell** - Abrir posición corta (apuesta a que el precio bajará)
3. **hold** - No hacer nada, esperar

### **Campos Importantes**

- **allocation_usd**: Cuánto dinero (USDT) usar en la operación
- **entry_price**: Precio al que se ejecutó la orden
- **tp_price**: Precio de take-profit (ganancia objetivo)
- **sl_price**: Precio de stop-loss (límite de pérdida)
- **rationale**: Explicación del LLM de por qué tomó esa decisión
- **filled**: Si la orden se ejecutó exitosamente

---

## 🎯 Comandos Útiles

### **Ver el diary en tiempo real:**
```powershell
Get-Content diary.jsonl -Wait -Tail 10
```

### **Contar cuántas operaciones se han hecho:**
```powershell
(Get-Content diary.jsonl | Select-String -Pattern '"action":"buy"').Count
(Get-Content diary.jsonl | Select-String -Pattern '"action":"sell"').Count
(Get-Content diary.jsonl | Select-String -Pattern '"action":"hold"').Count
```

### **Ver solo decisiones de BTC:**
```powershell
Get-Content diary.jsonl | Select-String -Pattern '"asset":"BTC"'
```

---

## 🔧 Solución de Problemas

### **Error: "Too Many Requests" (429)**
- **Causa**: Límite de rate de TAAPI alcanzado
- **Solución**: 
  - Espera unos minutos
  - O actualiza a un plan pago de TAAPI
  - O aumenta el intervalo (ej: de 5m a 15m)

### **El bot no hace trades**
- Verifica el diary: `http://localhost:3000/diary`
- Busca el campo `rationale` para ver por qué decidió "hold"
- El LLM puede estar siendo conservador

### **Quiero cambiar el intervalo**
Edita tu `.env`:
```bash
INTERVAL="15m"  # En lugar de 5m
```

### **Quiero cambiar los assets**
Edita tu `.env`:
```bash
ASSETS="BTC ETH"  # En lugar de BTC ETH SOL
```

---

## 📈 Métricas a Monitorear

1. **Balance**: ¿Está aumentando o disminuyendo?
2. **Win Rate**: ¿Cuántas operaciones son exitosas?
3. **Decisiones del LLM**: ¿Qué está pensando el bot?
4. **Posiciones abiertas**: ¿Cuántas posiciones activas hay?

---

## 🚀 Próximos Pasos

1. **Deja el bot correr** por unas horas
2. **Monitorea el diary** regularmente
3. **Revisa el balance** en Binance Testnet
4. **Analiza las decisiones** del LLM
5. **Ajusta parámetros** si es necesario

---

## ⚠️ Recordatorios Importantes

- ✅ Estás usando **TESTNET** (dinero virtual)
- ✅ No hay riesgo de perder dinero real
- ✅ Puedes experimentar libremente
- ⚠️ **NO** cambies `BINANCE_TESTNET=false` sin estar 100% seguro

---

**¡Feliz trading! 🎉**
