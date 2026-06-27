# Sube search.db indexado en tu PC hacia Railway
# Uso:
#   1. python scripts\ingest.py          (genera search.db)
#   2. En Railway: VZ_SEARCH_UPLOAD_TOKEN=un_secreto_largo
#   3. .\scripts\upload-db-to-railway.ps1 -Token "un_secreto_largo"

param(
    [string]$Url = "https://vz-search-production.up.railway.app/api/v1/ingest/database",
    [string]$DbPath = "search.db",
    [Parameter(Mandatory = $true)]
    [string]$Token
)

if (-not (Test-Path $DbPath)) {
    Write-Error "No existe $DbPath — ejecuta primero: python scripts\ingest.py"
    exit 1
}

$sizeMb = [math]::Round((Get-Item $DbPath).Length / 1MB, 2)
Write-Host "Subiendo $DbPath ($sizeMb MB) a Railway..."

curl.exe -f -X POST "$Url`?token=$Token" `
    -H "accept: application/json" `
    -F "file=@$DbPath"

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nListo. Prueba: $Url/../search?q=Gonzalez" -f ($Url -replace '/ingest/database','')
}
