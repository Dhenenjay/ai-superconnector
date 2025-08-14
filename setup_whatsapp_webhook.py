#!/usr/bin/env python
"""
Setup WhatsApp Webhook for Twilio
This script checks for messages and helps configure the webhook
"""

import requests
from services.connectors.twilio_connector import twilio_connector
import subprocess
import time
import sys

def check_recent_messages():
    """Check for recent WhatsApp messages"""
    print("📱 Checking for recent WhatsApp messages...")
    try:
        messages = twilio_connector.get_message_history(limit=10)
        if messages:
            print(f"\n✅ Found {len(messages)} recent messages:")
            for msg in messages[:5]:  # Show last 5
                if msg.get('body'):
                    direction = "Received" if msg['direction'] == 'inbound' else "Sent"
                    print(f"  - {direction}: {msg['body'][:100]}")
                    print(f"    From: {msg['from']}")
        else:
            print("❌ No messages found. Make sure you've joined the Twilio Sandbox.")
        return messages
    except Exception as e:
        print(f"❌ Error checking messages: {e}")
        return []

def test_webhook_locally():
    """Test the webhook endpoint locally"""
    print("\n🔧 Testing webhook endpoint locally...")
    try:
        # Simulate a WhatsApp message
        test_data = {
            "MessageSid": "TEST123",
            "From": "whatsapp:+1234567890",
            "To": "whatsapp:+18667972610",
            "Body": "Test message",
            "NumMedia": "0"
        }
        
        response = requests.post(
            "http://127.0.0.1:8088/twilio/webhook/whatsapp",
            data=test_data
        )
        
        if response.status_code == 200:
            print("✅ Webhook endpoint is working!")
            print(f"Response: {response.text[:200]}")
            return True
        else:
            print(f"❌ Webhook returned status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing webhook: {e}")
        return False

def setup_ngrok():
    """Instructions for setting up ngrok"""
    print("\n🌐 SETTING UP WEBHOOK WITH NGROK")
    print("=" * 60)
    print("\nTo receive WhatsApp messages, you need to expose your local server.")
    print("\n📋 OPTION 1: Using ngrok (Recommended for testing)")
    print("-" * 40)
    print("1. Download ngrok: https://ngrok.com/download")
    print("2. Sign up for free account: https://dashboard.ngrok.com/signup")
    print("3. Install ngrok:")
    print("   - Extract the downloaded file")
    print("   - Add to PATH or run from its directory")
    print("\n4. Authenticate ngrok:")
    print("   ngrok config add-authtoken YOUR_AUTH_TOKEN")
    print("\n5. Start ngrok tunnel:")
    print("   ngrok http 8088")
    print("\n6. Copy the HTTPS URL (e.g., https://abc123.ngrok.io)")
    print("\n7. Configure in Twilio Console:")
    print("   - Go to: https://console.twilio.com/develop/sms/try-it-out/whatsapp-learn")
    print("   - Set webhook URL: https://YOUR_NGROK_URL.ngrok.io/twilio/webhook/whatsapp")
    print("   - Method: POST")
    
    print("\n📋 OPTION 2: Quick setup with localtunnel")
    print("-" * 40)
    print("1. Install localtunnel:")
    print("   npm install -g localtunnel")
    print("\n2. Start tunnel:")
    print("   lt --port 8088")
    print("\n3. Use the provided URL in Twilio Console")
    
    print("\n⚠️  IMPORTANT NOTES:")
    print("-" * 40)
    print("• For WhatsApp Sandbox (testing):")
    print("  1. Send this message to +14155238886:")
    print("     'join <your-sandbox-keyword>'")
    print("  2. You'll get a confirmation message")
    print("  3. Then configure the webhook URL in Twilio Console")
    print("\n• Your Twilio WhatsApp number: +18667972610")
    print("• Webhook endpoint: /twilio/webhook/whatsapp")

def send_test_reply():
    """Send a test WhatsApp message"""
    print("\n📤 Want to send a test message?")
    phone = input("Enter your WhatsApp number (with country code, e.g., +1234567890): ")
    if phone:
        result = twilio_connector.send_whatsapp_message(
            to_number=phone,
            message="Hello! This is Eli, your AI Superconnector. I'm now configured to receive and respond to your messages!"
        )
        if result.get("success"):
            print(f"✅ Message sent! SID: {result['message_sid']}")
        else:
            print(f"❌ Failed to send: {result.get('error')}")

def main():
    print("=" * 60)
    print("🤖 WHATSAPP WEBHOOK SETUP FOR ELI SUPERCONNECTOR")
    print("=" * 60)
    
    # Check recent messages
    messages = check_recent_messages()
    
    # Test webhook locally
    test_webhook_locally()
    
    # Setup instructions
    setup_ngrok()
    
    # Offer to send test message
    print("\n" + "=" * 60)
    send_test = input("\nWould you like to send a test WhatsApp message? (y/n): ")
    if send_test.lower() == 'y':
        send_test_reply()
    
    print("\n✅ Setup complete! Follow the instructions above to configure your webhook.")
    print("\n📚 Quick Reference:")
    print("  - API Webhook: http://127.0.0.1:8088/twilio/webhook/whatsapp")
    print("  - Twilio Console: https://console.twilio.com")
    print("  - WhatsApp Number: +18667972610")

if __name__ == "__main__":
    main()
