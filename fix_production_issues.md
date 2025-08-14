# Production Deployment Fixes

## Issue 1: Session Persistence (Eli Forgetting Names)

The problem is that `UserSessionManager` stores sessions in local files, which don't persist on Render (ephemeral filesystem).

### Solution: Use Database or Redis for Sessions

**Option A: Use SQLite Database (Quick Fix)**
```python
# Modify services/user_session.py to use SQLAlchemy
# Sessions will be stored in the database instead of files
```

**Option B: Use Redis (Better for Production)**
1. Add Redis add-on in Render
2. Update session manager to use Redis

## Issue 2: Audio Streaming Issues

The OpenAI Realtime API audio issues are likely due to:
1. WebSocket connection timing
2. Audio format conversion problems
3. Network latency

### Fixes Already Applied:
1. ✅ Added user context to OpenAI session
2. ✅ Enabled initial greeting
3. ✅ Fixed audio conversion (PCM16 24kHz ↔ μ-law 8kHz)

### Additional Fixes Needed:

#### 1. Improve WebSocket Connection Handling
- Add connection retry logic
- Better error handling
- Connection health monitoring

#### 2. Debug Audio Path
- Add more detailed logging
- Verify audio is actually being received by OpenAI
- Check if Twilio stream configuration is correct

## Step-by-Step Deployment Guide

### 1. Update Your Render Environment Variables
```bash
# Make sure these are set in Render Dashboard:
OPENAI_API_KEY=sk-your-key
TWILIO_ACCOUNT_SID=your-sid
TWILIO_AUTH_TOKEN=your-token
PUBLIC_BASE_URL=https://your-app.onrender.com
```

### 2. Update Twilio Webhook URLs
Point your Twilio webhooks to:
- WhatsApp: `https://your-app.onrender.com/twilio/webhook/whatsapp`
- Voice: `https://your-app.onrender.com/twilio/webhook/voice/outbound`

### 3. Push Changes to GitHub
```bash
git add .
git commit -m "Fix session persistence and audio streaming"
git push origin main
```

### 4. Render will auto-deploy

## Testing Checklist

1. **Test WhatsApp Message**
   - Send a message with your name
   - Check if Eli remembers it in the next message

2. **Test Voice Call**
   - Request a call
   - Verify Eli greets you by name
   - Speak clearly and check if Eli responds appropriately

3. **Check Logs**
   - Monitor Render logs for errors
   - Look for "AUDIO TRACE" messages

## Do You Need Ngrok?

**NO!** You don't need ngrok (paid or free) because:
- ✅ Render provides a public HTTPS URL
- ✅ Render supports WebSockets
- ✅ Twilio can reach Render directly
- ✅ No firewall/NAT issues

Ngrok would only be needed if you were:
- Running locally for development
- Behind a corporate firewall
- Testing before deployment

## Quick Debugging Commands

```bash
# Check if backend is running
curl https://your-app.onrender.com/

# Test WebSocket connection
wscat -c wss://your-app.onrender.com/ws/realtime-bridge

# Check Twilio webhook status
curl -X POST https://your-app.onrender.com/twilio/webhook/whatsapp \
  -d "From=whatsapp:+1234567890" \
  -d "Body=Test message"
```
