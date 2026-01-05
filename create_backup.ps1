# Script de Backup del Bot de Trading
# Crea una copia completa del proyecto con timestamp

$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$projectName = "Ai_OldRafielKey"
$currentPath = Get-Location
$backupName = "${projectName}_BACKUP_${timestamp}"
$backupPath = Join-Path (Split-Path $currentPath -Parent) $backupName

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "💾 CREANDO BACKUP DEL BOT DE TRADING" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "📂 Proyecto actual: $currentPath" -ForegroundColor Yellow
Write-Host "📦 Backup destino: $backupPath" -ForegroundColor Yellow
Write-Host ""

# Crear directorio de backup
Write-Host "📁 Creando directorio de backup..." -ForegroundColor White
New-Item -ItemType Directory -Path $backupPath -Force | Out-Null

# Lista de archivos/carpetas a copiar
$itemsToCopy = @(
    "src",
    "docs",
    ".env",
    ".env.example",
    ".gitignore",
    "README.md",
    "BINANCE_QUICKSTART.md",
    "MONITORING_GUIDE.md",
    "pyproject.toml",
    "poetry.lock",
    "Dockerfile",
    "diary.jsonl",
    "env.binance.template",
    "test_binance_connection.py"
)

Write-Host "📋 Copiando archivos..." -ForegroundColor White
$copiedCount = 0
$skippedCount = 0

foreach ($item in $itemsToCopy) {
    $sourcePath = Join-Path $currentPath $item
    if (Test-Path $sourcePath) {
        try {
            Copy-Item -Path $sourcePath -Destination $backupPath -Recurse -Force
            Write-Host "  ✅ $item" -ForegroundColor Green
            $copiedCount++
        } catch {
            Write-Host "  ⚠️  Error copiando $item : $_" -ForegroundColor Yellow
            $skippedCount++
        }
    } else {
        Write-Host "  ⏭️  $item (no existe)" -ForegroundColor Gray
        $skippedCount++
    }
}

# Crear archivo README en el backup
$readmeContent = @"
# BACKUP DEL BOT DE TRADING
Fecha: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## Configuración Guardada

### Exchange
- Exchange: Binance Futures Testnet
- Modo: Paper Trading (dinero virtual)

### Trading
- Assets: BTC, ETH
- Intervalo: 15 minutos

### APIs Configuradas
- ✅ Binance API (Testnet)
- ✅ TAAPI (Indicadores técnicos)
- ✅ OpenRouter (LLM - Grok-4)

## Archivos Incluidos

- **src/**: Código fuente completo del bot
- **docs/**: Documentación
- **.env**: Configuración actual (¡MANTENER PRIVADO!)
- **diary.jsonl**: Historial de decisiones del bot
- **BINANCE_QUICKSTART.md**: Guía rápida de setup
- **MONITORING_GUIDE.md**: Guía de monitoreo

## Para Restaurar

1. Copia esta carpeta a donde quieras
2. Instala dependencias: ``pip install python-binance``
3. Ejecuta el bot: ``python src/main.py``

## Notas Importantes

⚠️ El archivo .env contiene tus API keys. NO lo compartas públicamente.
✅ Este backup incluye toda la configuración optimizada.
📊 El diary.jsonl contiene el historial de decisiones hasta la fecha del backup.

## Soporte

- Documentación completa: Ver MONITORING_GUIDE.md
- Setup rápido: Ver BINANCE_QUICKSTART.md
"@

$readmeContent | Out-File -FilePath (Join-Path $backupPath "BACKUP_README.txt") -Encoding UTF8

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "✅ BACKUP COMPLETADO" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 Estadísticas:" -ForegroundColor Yellow
Write-Host "  • Archivos copiados: $copiedCount" -ForegroundColor White
Write-Host "  • Archivos omitidos: $skippedCount" -ForegroundColor White
Write-Host ""
Write-Host "📂 Ubicación del backup:" -ForegroundColor Yellow
Write-Host "  $backupPath" -ForegroundColor White
Write-Host ""
Write-Host "💡 Contenido del backup:" -ForegroundColor Yellow
Write-Host "  • Código fuente completo" -ForegroundColor White
Write-Host "  • Configuración actual (.env)" -ForegroundColor White
Write-Host "  • Historial de decisiones (diary.jsonl)" -ForegroundColor White
Write-Host "  • Documentación completa" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  IMPORTANTE:" -ForegroundColor Red
Write-Host "  El archivo .env contiene tus API keys." -ForegroundColor White
Write-Host "  NO compartas este backup públicamente." -ForegroundColor White
Write-Host ""
Write-Host "✅ Puedes copiar esta carpeta a cualquier lugar" -ForegroundColor Green
Write-Host "   y el bot funcionará exactamente igual." -ForegroundColor Green
Write-Host ""

# Abrir la carpeta del backup
Write-Host "🔍 Abriendo carpeta del backup..." -ForegroundColor Cyan
Start-Process explorer.exe -ArgumentList $backupPath
