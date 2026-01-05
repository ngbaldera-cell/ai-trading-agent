# Configuración de Binance Testnet para Paper Trading

Esta guía te ayudará a configurar el bot para usar **Binance Futures Testnet** (dinero de prueba) en lugar de dinero real.

## 🎯 Ventajas del Testnet de Binance

- ✅ **Gratis**: Fondos de prueba ilimitados (15,000 USDT virtuales)
- ✅ **Sin riesgo**: No usas dinero real
- ✅ **Fácil configuración**: No requiere depósitos previos
- ✅ **Ambiente realista**: Simula el trading real con datos de mercado en vivo

## 📝 Paso 1: Crear Cuenta en Binance Futures Testnet

1. Ve a: **https://testnet.binancefuture.com/**
2. Haz clic en **"Register"** o **"Sign Up"**
3. Crea una cuenta con tu email (puede ser diferente a tu cuenta real de Binance)
4. Verifica tu email
5. Inicia sesión en el testnet

## 🔑 Paso 2: Generar API Keys

1. Una vez dentro del testnet, ve a tu perfil (esquina superior derecha)
2. Selecciona **"API Management"** o **"API Keys"**
3. Haz clic en **"Create API"** o **"Generate HMAC_SHA256 Key"**
4. Dale un nombre descriptivo (ej: "Trading Bot Test")
5. **Guarda tu API Key y API Secret** en un lugar seguro
   - ⚠️ **IMPORTANTE**: El Secret solo se muestra una vez

### Permisos Recomendados:
- ✅ Enable Reading
- ✅ Enable Futures
- ❌ Enable Withdrawals (NO necesario para testing)

## ⚙️ Paso 3: Configurar el Bot

1. Abre el archivo `.env` en la raíz del proyecto
2. Configura las siguientes variables:

```bash
# Seleccionar Binance como exchange
EXCHANGE=binance

# API Keys de Binance Testnet
BINANCE_API_KEY=tu_api_key_aqui
BINANCE_API_SECRET=tu_api_secret_aqui

# Asegurarse de usar TESTNET (muy importante!)
BINANCE_TESTNET=true

# Configuración de TAAPI (para indicadores técnicos)
TAAPI_API_KEY=tu_taapi_key_aqui

# Configuración de OpenRouter (para el LLM)
OPENROUTER_API_KEY=tu_openrouter_key_aqui
LLM_MODEL="x-ai/grok-4"

# Assets a tradear
ASSETS="BTC ETH SOL"
INTERVAL="5m"
```

## 🚀 Paso 4: Instalar Dependencias

Ejecuta el siguiente comando para instalar las nuevas dependencias:

```bash
poetry install
```

O si usas pip:

```bash
pip install python-binance
```

## ▶️ Paso 5: Ejecutar el Bot

```bash
poetry run python src/main.py
```

O especificando assets e intervalo manualmente:

```bash
poetry run python src/main.py --assets BTC ETH --interval 5m
```

## 🔍 Verificación

Cuando el bot inicie correctamente, deberías ver:

```
🧪 Binance client initialized in TESTNET mode (paper trading)
🔄 Using Binance exchange
Starting trading agent for assets: ['BTC', 'ETH'] at interval: 5m
```

## 📊 Monitoreo

El bot expone endpoints HTTP para monitorear:

- **Diary**: `http://localhost:3000/diary` - Historial de decisiones
- **Logs**: `http://localhost:3000/logs` - Logs del sistema

## ⚠️ Importante: Cambiar a Producción

**NUNCA** cambies a producción sin estar 100% seguro. Para usar dinero real:

1. Cambia `BINANCE_TESTNET=false` en `.env`
2. Usa API Keys de tu cuenta **real** de Binance
3. ⚠️ **RIESGO TOTAL**: Puedes perder dinero real

## 🆘 Solución de Problemas

### Error: "BINANCE_API_KEY and BINANCE_API_SECRET must be provided"
- Verifica que hayas configurado correctamente las variables en `.env`
- Asegúrate de que no haya espacios extra

### Error: "Invalid API-key, IP, or permissions"
- Verifica que las API keys sean correctas
- Asegúrate de que los permisos incluyan "Enable Futures"
- Si configuraste restricción de IP, agrégala en la configuración de la API

### El bot no ejecuta trades
- Verifica que tengas fondos en tu cuenta de testnet
- Revisa los logs para ver las decisiones del LLM
- Asegúrate de que TAAPI_API_KEY y OPENROUTER_API_KEY estén configurados

## 📚 Recursos Adicionales

- [Binance Futures Testnet](https://testnet.binancefuture.com/)
- [Documentación de Binance API](https://binance-docs.github.io/apidocs/futures/en/)
- [Python-Binance Docs](https://python-binance.readthedocs.io/)

## 🔄 Volver a Hyperliquid

Si quieres volver a usar Hyperliquid, simplemente cambia en `.env`:

```bash
EXCHANGE=hyperliquid
```
