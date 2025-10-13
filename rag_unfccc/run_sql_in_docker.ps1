# Run all SQL files in Docker container
$separator = "============================================================"
Write-Host $separator -ForegroundColor Cyan
Write-Host "Running SQL Setup Files in Docker Container" -ForegroundColor Yellow
Write-Host $separator -ForegroundColor Cyan

$sqlFiles = Get-ChildItem -Path ".\sql\*.sql" | Sort-Object Name
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
