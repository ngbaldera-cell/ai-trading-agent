# Script para actualizar configuración del bot
# Aplica las optimizaciones recomendadas

$envFile = ".env"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "🔧 ACTUALIZANDO CONFIGURACIÓN DEL BOT" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Leer el archivo .env actual
$content = Get-Content $envFile -Raw

Write-Host "📝 Aplicando optimizaciones:" -ForegroundColor Yellow
Write-Host ""

# Optimización 1: Cambiar intervalo de 5m a 15m
if ($content -match 'INTERVAL="?5m"?') {
    $content = $content -replace 'INTERVAL="?5m"?', 'INTERVAL="15m"'
    Write-Host "  ✅ Intervalo cambiado: 5m → 15m" -ForegroundColor Green
} elseif ($content -match 'INTERVAL="?15m"?') {
    Write-Host "  ℹ️  Intervalo ya está en 15m" -ForegroundColor Gray
} else {
    # Si no existe, agregarlo
    $content += "`nINTERVAL=`"15m`""
    Write-Host "  ✅ Intervalo agregado: 15m" -ForegroundColor Green
}

# Optimización 2: Reducir assets de BTC ETH SOL a BTC ETH
if ($content -match 'ASSETS="?BTC ETH SOL"?') {
    $content = $content -replace 'ASSETS="?BTC ETH SOL"?', 'ASSETS="BTC ETH"'
    Write-Host "  ✅ Assets reducidos: BTC ETH SOL → BTC ETH" -ForegroundColor Green
} elseif ($content -match 'ASSETS="?BTC,ETH,SOL"?') {
    $content = $content -replace 'ASSETS="?BTC,ETH,SOL"?', 'ASSETS="BTC ETH"'
    Write-Host "  ✅ Assets reducidos: BTC,ETH,SOL → BTC ETH" -ForegroundColor Green
} elseif ($content -match 'ASSETS="?BTC ETH"?') {
    Write-Host "  ℹ️  Assets ya están optimizados (BTC ETH)" -ForegroundColor Gray
} else {
    Write-Host "  ⚠️  No se encontró ASSETS en el .env" -ForegroundColor Yellow
}

# Guardar el archivo actualizado
$content | Set-Content $envFile -NoNewline

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "✅ CONFIGURACIÓN ACTUALIZADA" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 Nueva configuración:" -ForegroundColor Yellow
Write-Host "  • Intervalo: 15 minutos (reduce llamadas a TAAPI)" -ForegroundColor White
Write-Host "  • Assets: BTC y ETH (reduce carga)" -ForegroundColor White
Write-Host ""
Write-Host "🎯 Beneficios:" -ForegroundColor Yellow
Write-Host "  • Menos errores de TAAPI (429)" -ForegroundColor White
Write-Host "  • Más tiempo para análisis de mercado" -ForegroundColor White
Write-Host "  • Mejor calidad de datos" -ForegroundColor White
Write-Host ""
Write-Host "🚀 Reinicia el bot con: python src/main.py" -ForegroundColor Cyan
Write-Host ""
