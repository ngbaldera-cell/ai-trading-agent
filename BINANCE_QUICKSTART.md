# 🚀 Guía Rápida: Configuración con Binance Testnet

Esta guía te ayudará a configurar el bot de trading para usar **Binance Futures Testnet** (dinero de prueba) en lugar de dinero real.

## ✅ ¿Por qué usar Binance Testnet?

- 💰 **Fondos gratis**: 15,000 USDT virtuales para testear
- 🛡️ **Sin riesgo**: No usas dinero real
- 🚀 **Fácil setup**: No requiere depósitos previos (a diferencia de Hyperliquid)
- 📊 **Datos reales**: Opera con datos de mercado en vivo

---

## 📋 Pasos de Configuración

### 1️⃣ Crear Cuenta en Binance Testnet

1. Ve a: **https://testnet.binancefuture.com/**
2. Registra una cuenta nueva (puede ser diferente a tu cuenta real de Binance)
3. Verifica tu email e inicia sesión

### 2️⃣ Generar API Keys

1. En el testnet, ve a tu perfil → **API Management**
2. Crea una nueva API Key (tipo: **HMAC_SHA256**)
3. **Guarda tu API Key y Secret** (el secret solo se muestra una vez)

**Permisos necesarios:**
- ✅ Enable Reading
- ✅ Enable Futures
- ❌ Enable Withdrawals (NO necesario)

### 3️⃣ Configurar Variables de Entorno

Copia el archivo de ejemplo y edítalo:

```bash
# En Windows
copy env.binance.template .env

# En Linux/Mac
cp env.binance.template .env
```

Luego edita `.env` con tus credenciales:

```bash
# Exchange a usar
EXCHANGE=binance

# API Keys de Binance Testnet
BINANCE_API_KEY=tu_api_key_aqui
BINANCE_API_SECRET=tu_api_secret_aqui
BINANCE_TESTNET=true

# TAAPI para indicadores técnicos
TAAPI_API_KEY=tu_taapi_key_aqui

# OpenRouter para el LLM
OPENROUTER_API_KEY=tu_openrouter_key_aqui
LLM_MODEL="x-ai/grok-4"

# Configuración de trading
ASSETS="BTC ETH SOL"
INTERVAL="5m"
```

### 4️⃣ Instalar Dependencias

```bash
pip install python-binance
```

O si usas Poetry:

```bash
poetry install
```

### 5️⃣ Ejecutar el Bot

```bash
python src/main.py
```

O con Poetry:

```bash
poetry run python src/main.py
```

---

## ✅ Verificación

Si todo está configurado correctamente, deberías ver:

```
🧪 Binance client initialized in TESTNET mode (paper trading)
🔄 Using Binance exchange
Starting trading agent for assets: ['BTC', 'ETH', 'SOL'] at interval: 5m
```

---

## 📊 Monitoreo del Bot

El bot expone endpoints HTTP para monitorear su actividad:

- **Diary**: http://localhost:3000/diary
- **Logs**: http://localhost:3000/logs

---

## 🔄 Cambiar entre Exchanges

### Para usar Binance:
```bash
EXCHANGE=binance
```

### Para usar Hyperliquid:
```bash
EXCHANGE=hyperliquid
```

---

## ⚠️ IMPORTANTE: Producción vs Testnet

### Para Testnet (RECOMENDADO para pruebas):
```bash
BINANCE_TESTNET=true
```

### Para Producción (DINERO REAL - ALTO RIESGO):
```bash
BINANCE_TESTNET=false
# Y usa API keys de tu cuenta REAL de Binance
```

⚠️ **NUNCA** cambies a producción sin estar 100% seguro de lo que haces.

---

## 🆘 Solución de Problemas

### Error: "BINANCE_API_KEY and BINANCE_API_SECRET must be provided"
- Verifica que las variables estén en `.env`
- No debe haber espacios extra alrededor del `=`

### Error: "Invalid API-key, IP, or permissions"
- Verifica que las API keys sean correctas
- Asegúrate de tener permisos de "Enable Futures"
- Si configuraste restricción de IP, agrégala en Binance

### El bot no ejecuta trades
- Verifica que tengas fondos en tu cuenta de testnet
- Revisa los logs: `http://localhost:3000/logs`
- Asegúrate de que TAAPI_API_KEY y OPENROUTER_API_KEY estén configurados

---

## 📚 Recursos

- [Binance Futures Testnet](https://testnet.binancefuture.com/)
- [Documentación Binance API](https://binance-docs.github.io/apidocs/futures/en/)
- [Documentación Completa](docs/BINANCE_TESTNET_SETUP.md)

---

## 🎓 Siguiente Paso

Una vez que el bot esté funcionando en testnet y estés satisfecho con los resultados, puedes:

1. Analizar las decisiones en el diary
2. Ajustar los parámetros del LLM
3. Modificar los assets y el intervalo
4. **Solo cuando estés 100% seguro**, considerar usar dinero real

**¡Buena suerte con tu trading bot! 🚀**
