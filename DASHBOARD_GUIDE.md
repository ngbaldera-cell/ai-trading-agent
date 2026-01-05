# 🎮 GUÍA DEL DASHBOARD - Trading Bot

## 🚀 Cómo Acceder al Dashboard

1. **Asegúrate de que el bot esté corriendo:**
   ```bash
   python src/main.py
   ```

2. **Abre tu navegador y ve a:**
   ```
   http://localhost:3000
   ```
   o
   ```
   http://localhost:3000/dashboard
   ```

---

## 📊 Características del Dashboard

### **1. Header - Información General**
- **Status Indicator**: Luz verde = bot corriendo, roja = pausado
- **Exchange**: Muestra qué exchange estás usando (Binance Testnet)
- **Balance**: Tu balance actual en USDT
- **Assets**: Qué criptomonedas está monitoreando
- **Interval**: Cada cuánto analiza el mercado

### **2. Controles del Bot**
- **⏸️ PAUSE BOT**: Pausa el bot (no hará más análisis ni trades)
- **▶️ START BOT**: Reanuda el bot
- **🔄 REFRESH**: Actualiza manualmente los datos
- **❌ CLOSE ALL POSITIONS**: Cierra TODAS las posiciones abiertas (¡cuidado!)

### **3. Next Decision - Countdown**
- Muestra cuánto falta para el próximo análisis
- Se actualiza en tiempo real
- Formato: MM:SS (minutos:segundos)

### **4. Account Metrics**
- **Total Value**: Valor total de tu cuenta
- **Available Balance**: Balance disponible para tradear
- **Total P&L**: Ganancia/Pérdida total
  - Verde = ganancia
  - Rojo = pérdida
- **Total Trades**: Número total de operaciones
- **Win Rate**: Porcentaje de trades exitosos

### **5. Open Positions**
Tabla con todas tus posiciones abiertas:
- **ASSET**: Qué criptomoneda (BTC, ETH, etc.)
- **SIDE**: LONG (compra) o SHORT (venta)
- **SIZE**: Cantidad de contratos
- **ENTRY**: Precio de entrada
- **CURRENT**: Precio actual
- **P&L**: Ganancia/Pérdida de esa posición
- **ACTIONS**:
  - **💰 TP**: Tomar profit (cerrar con ganancia)
  - **❌ CLOSE**: Cerrar la posición inmediatamente

### **6. Recent Decisions**
Historial de las últimas decisiones del bot:
- **BUY** (verde): El bot decidió comprar
- **SELL** (rojo): El bot decidió vender
- **HOLD** (amarillo): El bot decidió no hacer nada
- Incluye la razón (rationale) de cada decisión
- Muestra la hora de cada decisión

---

## 🎨 Estilo Visual

El dashboard tiene un estilo **retro/terminal** inspirado en tu screenshot:
- Fondo negro (#1a1a1a)
- Texto verde tipo terminal (#00ff00)
- Bordes verdes estilo ASCII
- Fuente monoespaciada (Courier New)
- Efectos de pulso en los indicadores de estado

---

## 🔄 Actualización Automática

El dashboard se actualiza automáticamente cada **5 segundos**:
- Balance y métricas
- Posiciones abiertas
- Decisiones recientes
- Countdown del próximo análisis

---

## ⚡ Acciones Rápidas

### **Pausar el Bot**
1. Click en "⏸️ PAUSE BOT"
2. El bot dejará de analizar y tradear
3. El indicador se pondrá rojo
4. Las posiciones abiertas NO se cierran automáticamente

### **Cerrar una Posición**
1. Ve a la tabla "OPEN POSITIONS"
2. Encuentra la posición que quieres cerrar
3. Click en "❌ CLOSE"
4. Confirma la acción
5. La posición se cierra inmediatamente

### **Tomar Profit**
1. Ve a la tabla "OPEN POSITIONS"
2. Click en "💰 TP" en la posición deseada
3. Confirma
4. Se cierra la posición al precio actual

### **Cerrar Todas las Posiciones**
⚠️ **CUIDADO**: Esta acción cierra TODAS las posiciones
1. Click en "❌ CLOSE ALL POSITIONS" (botón rojo)
2. Confirma la acción
3. Todas las posiciones se cierran

---

## 📱 Compatibilidad

El dashboard funciona en:
- ✅ Chrome
- ✅ Firefox
- ✅ Edge
- ✅ Safari
- ✅ Móviles (responsive)

---

## 🔧 Solución de Problemas

### **El dashboard no carga**
- Verifica que el bot esté corriendo: `python src/main.py`
- Asegúrate de ir a `http://localhost:3000`
- Revisa que el puerto 3000 no esté ocupado

### **Los datos no se actualizan**
- Click en "🔄 REFRESH"
- Verifica que el bot esté corriendo (no pausado)
- Revisa la consola del navegador (F12) por errores

### **Error al cerrar posiciones**
- Verifica que la posición aún exista
- Asegúrate de que el bot tenga conexión con Binance
- Revisa los logs del bot en la terminal

### **El countdown no funciona**
- Refresca la página (F5)
- Verifica que el bot esté corriendo
- El countdown se resetea después de cada análisis

---

## 💡 Tips y Trucos

1. **Deja el dashboard abierto** en una pestaña para monitorear en tiempo real
2. **Usa el botón PAUSE** si quieres analizar manualmente antes de que el bot haga un trade
3. **Revisa el "rationale"** en Recent Decisions para entender por qué el bot tomó cada decisión
4. **El dashboard es solo para monitoreo y control** - el bot sigue funcionando en segundo plano
5. **Puedes tener múltiples pestañas** del dashboard abiertas simultáneamente

---

## 🎯 Atajos de Teclado (Próximamente)

En futuras versiones se agregarán:
- `Space`: Pausar/Reanudar bot
- `R`: Refresh
- `C`: Cerrar todas las posiciones
- `Esc`: Cancelar acción

---

## 📊 Datos que Muestra

Todos los datos son **en tiempo real** desde:
- **Binance API**: Precios, posiciones, balance
- **Bot interno**: Decisiones, análisis, métricas
- **Diary**: Historial completo de decisiones

---

## ⚠️ Importante

- El dashboard **NO** reemplaza el monitoreo en Binance
- Siempre verifica en **https://testnet.binancefuture.com/**
- Las acciones del dashboard son **inmediatas** y **no se pueden deshacer**
- Usa el botón "CLOSE ALL" con **extrema precaución**

---

## 🚀 Próximas Mejoras

Funcionalidades planeadas:
- [ ] Gráficos de P&L en tiempo real
- [ ] Alertas y notificaciones
- [ ] Modo oscuro/claro
- [ ] Exportar datos a CSV
- [ ] Configuración de parámetros desde el dashboard
- [ ] Historial de trades con filtros
- [ ] Análisis de rendimiento por asset

---

**¡Disfruta tu nuevo dashboard! 🎉**

Para cualquier duda, revisa la documentación principal o los logs del bot.
