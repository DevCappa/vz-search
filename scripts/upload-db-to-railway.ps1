# Sube search.db indexado en tu PC hacia Railway
# Uso:
#   1. python scripts\ingest.py
#   2. En Railway: VZ_SEARCH_UPLOAD_TOKEN=un_secreto_largo
#   3. .\scripts\upload-db-to-railway.ps1 -Token "un_secreto_largo"

param(
    [string]$Url = "https://vz-search-production.up.railway.app/api/v1/ingest/database",
    [string]$DbPath = "search.db",
    [Parameter(Mandatory = $true)]
    [string]$Token
)

if (-not (Test-Path $DbPath)) {
    Write-Error "No existe $DbPath. Ejecuta primero: python scripts\ingest.py"
    exit 1
}

$fileSize = (Get-Item $DbPath).Length
$sizeMb = [math]::Round($fileSize / 1048576, 2)
Write-Host "Subiendo $DbPath ($sizeMb megabytes) a Railway..."

$encodedToken = [uri]::EscapeDataString($Token)
if ($Url.Contains('?')) {
    $uploadUrl = "$Url" + '&token=' + $encodedToken
} else {
    $uploadUrl = "$Url" + '?token=' + $encodedToken
}

curl.exe -f -X PUT $uploadUrl `
    -H "Content-Type: application/octet-stream" `
    --data-binary "@$DbPath"

if ($LASTEXITCODE -eq 0) {
    $base = ($Url -split '/api/')[0]
    $searchUrl = $base + '/api/v1/search?q=Gonzalez'
    Write-Host ''
    Write-Host 'Listo. Prueba busqueda en:'
    Write-Host $searchUrl
}
