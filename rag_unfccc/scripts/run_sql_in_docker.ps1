# Windows Docker Workaround: Run all SQL files in Docker container
# 
# This script is a workaround for Windows Docker Desktop networking issues
# that prevent direct PostgreSQL connections. It runs SQL schema files
# directly inside the Docker container using docker exec.
#
# Usage: .\scripts\run_sql_in_docker.ps1
# Requirements: Docker container named 'NDC_rag' must be running
#
# See README.md and Issues_tracking/KNOWN_ISSUES.md (Issue #2) for details.

$separator = "============================================================"
Write-Host $separator -ForegroundColor Cyan
Write-Host "Running SQL Setup Files in Docker Container (Windows Workaround)" -ForegroundColor Yellow
Write-Host $separator -ForegroundColor Cyan

# Get script directory and find sql folder relative to project root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$sqlPath = Join-Path $projectRoot "sql\*.sql"

$sqlFiles = Get-ChildItem -Path $sqlPath | Sort-Object Name
$successCount = 0
$failCount = 0

foreach ($file in $sqlFiles) {
    Write-Host ""
    Write-Host "Executing $($file.Name)..." -ForegroundColor Cyan
    
    # Read file content and pipe to docker exec
    $content = Get-Content $file.FullName -Raw
    $content | docker exec -i NDC_rag psql -U climate -d climate
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Success!" -ForegroundColor Green
        $successCount++
    } else {
        Write-Host "  Failed!" -ForegroundColor Red
        $failCount++
    }
}

Write-Host ""
Write-Host $separator -ForegroundColor Cyan
$summary = "Complete! Success: $successCount | Failed: $failCount"
if ($failCount -eq 0) {
    Write-Host $summary -ForegroundColor Green
} else {
    Write-Host $summary -ForegroundColor Yellow
}
Write-Host $separator -ForegroundColor Cyan
