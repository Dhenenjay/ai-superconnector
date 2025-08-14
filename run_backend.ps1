# Script to run the backend server in a new terminal window
# This allows the backend to run independently without blocking your main terminal

# Activate virtual environment and run the server
$scriptBlock = {
    Set-Location "C:\Users\Dhenenjay\ai-superconnector"
    
    Write-Host "=================================" -ForegroundColor Cyan
    Write-Host "Starting AI Superconnector Backend" -ForegroundColor Cyan
    Write-Host "=================================" -ForegroundColor Cyan
    
    # Activate virtual environment
    if (Test-Path ".venv\Scripts\Activate.ps1") {
        Write-Host "Activating virtual environment..." -ForegroundColor Yellow
        & ".\.venv\Scripts\Activate.ps1"
    } else {
        Write-Host "Warning: Virtual environment not found" -ForegroundColor Red
    }
    
    # Display server info
    Write-Host "`nServer starting on: http://localhost:8000" -ForegroundColor Green
    Write-Host "API Documentation: http://localhost:8000/docs" -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop the server`n" -ForegroundColor Yellow
    
    # Run the FastAPI server with auto-reload for development
    python -m uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug
    
    # Keep window open if server crashes
    Write-Host "`nServer stopped. Press any key to close this window..." -ForegroundColor Red
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# Start new PowerShell window with the script
Start-Process powershell -ArgumentList "-NoExit", "-Command", $scriptBlock
