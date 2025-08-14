# 🚀 Deployment Guide

## Quick Deploy Options

### 1. Deploy to Render (Recommended)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Dhenenjay/ai-superconnector)

1. Click the button above
2. Connect your GitHub account
3. Set environment variables:
   - `OPENAI_API_KEY`
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_API_KEY`
   - `TWILIO_API_SECRET`
   - `TWILIO_PHONE_NUMBER`
4. Click "Create Web Service"

### 2. Deploy to Railway
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up

# Set environment variables
railway variables set OPENAI_API_KEY=sk-proj-...
railway variables set TWILIO_ACCOUNT_SID=AC...
```

### 3. Deploy to Heroku
```bash
# Create app
heroku create your-app-name

# Set environment variables
heroku config:set OPENAI_API_KEY=sk-proj-...
heroku config:set TWILIO_ACCOUNT_SID=AC...

# Deploy
git push heroku main
```

## After Deployment

### 1. Update Twilio Webhooks
Go to [Twilio Console](https://console.twilio.com) and update:

**WhatsApp Webhook:**
```
https://your-app.onrender.com/twilio/webhook/whatsapp
```

**Voice Webhook:**
```
https://your-app.onrender.com/twilio/webhook/voice/outbound
```

### 2. Test Your Deployment

**Test API Health:**
```bash
curl https://your-app.onrender.com/
```

**Test WhatsApp:**
```bash
curl -X POST https://your-app.onrender.com/twilio/whatsapp/send \
  -H "Content-Type: application/json" \
  -d '{"to_number": "+1234567890", "message": "Hello from API!"}'
```

**Test Voice Call:**
```bash
curl -X POST https://your-app.onrender.com/twilio/voice/call \
  -H "Content-Type: application/json" \
  -d '{"to_number": "+1234567890", "message": "Hello, this is a test call"}'
```

## Production Checklist

- [ ] Set all environment variables
- [ ] Update Twilio webhook URLs
- [ ] Enable HTTPS (automatic on Render/Railway/Heroku)
- [ ] Set up monitoring (e.g., Sentry)
- [ ] Configure custom domain (optional)
- [ ] Set up auto-deploy from GitHub
- [ ] Test WhatsApp messaging
- [ ] Test voice calls with OpenAI
- [ ] Monitor logs for errors

## Troubleshooting

### WebSocket Issues
- Ensure your hosting platform supports WebSocket connections
- Check that the WebSocket URL uses `wss://` for HTTPS deployments

### Twilio Connection Issues
- Verify all Twilio credentials are correctly set
- Check Twilio webhook URLs are accessible
- Ensure phone numbers are in E.164 format (+1234567890)

### OpenAI Realtime Issues
- Confirm OPENAI_API_KEY has access to realtime models
- Check audio format compatibility (μ-law 8kHz ↔ PCM16 24kHz)

## Support

- [GitHub Issues](https://github.com/Dhenenjay/ai-superconnector/issues)
- [Twilio Docs](https://www.twilio.com/docs)
- [OpenAI Docs](https://platform.openai.com/docs)
