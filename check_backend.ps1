# Simple script to check backend status
Write-Host "Checking backend status..." -ForegroundColor Cyan

# Check for running processes
Write-Host "`nRunning processes:" -ForegroundColor Yellow
Get-Process | Where-Object {$_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*"} | Format-Table Id, ProcessName, CPU, StartTime -AutoSize

# Test backend connection
Write-Host "`nTesting backend at http://localhost:8000..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000" -Method GET -ErrorAction Stop
    Write-Host "Backend is RUNNING" -ForegroundColor Green
    Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Green
}
catch {
    Write-Host "Backend is NOT running" -ForegroundColor Red
    Write-Host "Start it with: .\start_backend.bat" -ForegroundColor Yellow
}

Write-Host "`nTo start backend in new window: .\start_backend.bat" -ForegroundColor Cyan
