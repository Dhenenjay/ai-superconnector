# Start Ngrok Tunnel for WhatsApp Webhook
Write-Host ""
Write-Host "🚀 STARTING NGROK TUNNEL FOR WHATSAPP WEBHOOK" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor DarkGray
Write-Host ""

$ngrokPath = "C:\Users\Dhenenjay\tools\ngrok\ngrok.exe"

# Check if ngrok is authenticated
Write-Host "📝 Checking ngrok authentication..." -ForegroundColor Yellow
$configPath = "$env:USERPROFILE\.ngrok2\ngrok.yml"
if (Test-Path $configPath) {
    Write-Host "✅ Ngrok is configured" -ForegroundColor Green
} else {
    Write-Host "⚠️  Ngrok needs authentication (optional for basic use)" -ForegroundColor Yellow
    Write-Host "   To authenticate (for longer sessions):" -ForegroundColor Gray
    Write-Host "   1. Sign up at: https://dashboard.ngrok.com/signup" -ForegroundColor Gray
    Write-Host "   2. Get your authtoken from dashboard" -ForegroundColor Gray
    Write-Host "   3. Run: & '$ngrokPath' config add-authtoken YOUR_TOKEN" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "🌐 Starting ngrok tunnel on port 8000..." -ForegroundColor Green
Write-Host ""
Write-Host "IMPORTANT: After ngrok starts:" -ForegroundColor Yellow
Write-Host "1. Copy the HTTPS URL (e.g., https://abc123.ngrok-free.app)" -ForegroundColor White
Write-Host "2. Go to: https://console.twilio.com" -ForegroundColor White
Write-Host "3. Navigate to: Messaging > Try it out > WhatsApp > Sandbox Settings" -ForegroundColor White
Write-Host "4. Set 'When a message comes in' to:" -ForegroundColor White
Write-Host "   https://YOUR-NGROK-URL.ngrok-free.app/twilio/webhook/whatsapp" -ForegroundColor Cyan
Write-Host "5. Method: POST" -ForegroundColor White
Write-Host "6. Click Save" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to start ngrok..." -ForegroundColor Green
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Start ngrok
& $ngrokPath http 8000
