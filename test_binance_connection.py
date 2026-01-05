"""Script de prueba para verificar la conexión con Binance Testnet"""

import os
from dotenv import load_dotenv
from binance.client import Client

# Cargar variables de entorno
load_dotenv()

# Obtener credenciales
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")
use_testnet = os.getenv("BINANCE_TESTNET", "true").lower() in ["true", "1", "yes"]

print("=" * 60)
print("🔍 DIAGNÓSTICO DE CONEXIÓN BINANCE")
print("=" * 60)

# Verificar que las variables existan
print(f"\n✓ API Key encontrada: {api_key[:20]}..." if api_key else "❌ API Key NO encontrada")
print(f"✓ API Secret encontrada: {api_secret[:20]}..." if api_secret else "❌ API Secret NO encontrada")
print(f"✓ Modo Testnet: {use_testnet}")

if not api_key or not api_secret:
    print("\n❌ ERROR: Faltan credenciales en el archivo .env")
    print("\nAsegúrate de tener estas líneas en tu .env:")
    print("BINANCE_API_KEY=tu_api_key_aqui")
    print("BINANCE_API_SECRET=tu_api_secret_aqui")
    exit(1)

# Intentar conectar
print("\n" + "=" * 60)
print("🔌 INTENTANDO CONECTAR...")
print("=" * 60)

try:
    client = Client(api_key, api_secret, testnet=use_testnet)
    print("✓ Cliente inicializado correctamente")
    
    # Probar obtener información de la cuenta
    print("\n📊 Obteniendo información de la cuenta...")
    account = client.futures_account()
    
    print("\n✅ ¡CONEXIÓN EXITOSA!")
    print("=" * 60)
    
    # Mostrar balance
    balance = float(account.get("availableBalance", 0))
    total_balance = float(account.get("totalWalletBalance", 0))
    
    print(f"\n💰 Balance disponible: {balance:.2f} USDT")
    print(f"💼 Balance total: {total_balance:.2f} USDT")
    
    # Mostrar posiciones activas
    positions = [p for p in account.get("positions", []) if float(p.get("positionAmt", 0)) != 0]
    if positions:
        print(f"\n📈 Posiciones activas: {len(positions)}")
        for pos in positions:
            symbol = pos.get("symbol")
            amount = float(pos.get("positionAmt", 0))
            print(f"  - {symbol}: {amount}")
    else:
        print("\n📭 No hay posiciones activas")
    
    print("\n" + "=" * 60)
    print("✅ Tu configuración está CORRECTA")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ ERROR AL CONECTAR:")
    print(f"   {str(e)}")
    print("\n" + "=" * 60)
    print("🔧 POSIBLES SOLUCIONES:")
    print("=" * 60)
    print("\n1. Verifica que las API Keys sean del TESTNET:")
    print("   https://testnet.binancefuture.com/")
    print("\n2. Asegúrate de que 'Enable Reading' esté marcado")
    print("\n3. Verifica que NO haya restricción de IP")
    print("\n4. Regenera las API Keys si las compartiste públicamente")
    print("\n5. Verifica que no haya espacios extra en el .env:")
    print("   ❌ BINANCE_API_KEY = tu_key")
    print("   ✅ BINANCE_API_KEY=tu_key")
