# Actualizar configuración del bot
$envFile = ".env"
$content = Get-Content $envFile -Raw

# Cambiar intervalo
$content = $content -replace 'INTERVAL=5m', 'INTERVAL=15m'
$content = $content -replace 'INTERVAL="5m"', 'INTERVAL="15m"'

# Cambiar assets
$content = $content -replace 'ASSETS=BTC ETH SOL', 'ASSETS=BTC ETH'
$content = $content -replace 'ASSETS="BTC ETH SOL"', 'ASSETS="BTC ETH"'

# Guardar
$content | Set-Content $envFile -NoNewline

Write-Host "✅ Configuración actualizada:" -ForegroundColor Green
Write-Host "  • Intervalo: 15m" -ForegroundColor White
Write-Host "  • Assets: BTC ETH" -ForegroundColor White
