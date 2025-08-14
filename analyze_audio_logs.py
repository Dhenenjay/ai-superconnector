#!/usr/bin/env python3
"""
Analyze audio logs to identify issues with Twilio-OpenAI audio bridge
"""
import re
import sys
from collections import defaultdict
from datetime import datetime

def analyze_logs(log_file_path):
    """Analyze logs for audio processing issues"""
    
    stats = {
        'twilio_events': defaultdict(int),
        'audio_received': [],
        'audio_sent_to_openai': [],
        'commits': [],
        'errors': [],
        'silent_frames': 0,
        'non_silent_frames': 0,
        'openai_buffer_state': [],
        'echo_attempts': 0,
        'test_tones': 0,
        'openai_responses': [],
        'empty_buffer_errors': 0
    }
    
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Log file not found: {log_file_path}")
        return
    
    for i, line in enumerate(lines):
        # Track Twilio events
        if 'Received Twilio event:' in line:
            match = re.search(r'Received Twilio event: (\w+)', line)
            if match:
                stats['twilio_events'][match.group(1)] += 1
        
        # Track audio received from Twilio
        if '[AUDIO TRACE] Received from Twilio:' in line:
            match = re.search(r'Received from Twilio: (\d+) bytes', line)
            if match:
                stats['audio_received'].append(int(match.group(1)))
        
        # Track silent vs non-silent frames
        if '[AUDIO TRACE] Processing frame' in line:
            if 'silent=True' in line:
                stats['silent_frames'] += 1
            elif 'silent=False' in line:
                stats['non_silent_frames'] += 1
        
        # Track audio sent to OpenAI
        if '[AUDIO TRACE] Sent to OpenAI:' in line:
            if 'success=True' in line:
                stats['audio_sent_to_openai'].append('success')
            elif 'success=False' in line:
                stats['audio_sent_to_openai'].append('failed')
            elif 'success=None' in line:
                stats['audio_sent_to_openai'].append('error')
        
        # Track OpenAI buffer state
        if '[OPENAI TRACE] Appended' in line:
            match = re.search(r'total buffered: ([\d.]+)ms', line)
            if match:
                stats['openai_buffer_state'].append(float(match.group(1)))
        
        # Track commits
        if '[AUDIO TRACE] Committing after' in line or '[OPENAI TRACE] Committed' in line:
            match = re.search(r'(\d+) chunks|with ([\d.]+)ms', line)
            if match:
                stats['commits'].append(line.strip())
        
        # Track commit skips
        if '[OPENAI TRACE] Skipping commit:' in line:
            stats['commits'].append(f"SKIPPED: {line.strip()}")
        
        # Track errors
        if 'ERROR' in line or 'error' in line:
            if 'input_audio_buffer_commit_empty' in line:
                stats['empty_buffer_errors'] += 1
            stats['errors'].append(line.strip()[:200])  # First 200 chars
        
        # Track echo attempts
        if 'MEDIA_ECHO_BACK is enabled' in line:
            stats['echo_attempts'] += 1
        
        # Track test tones
        if 'Sent.*test tone to Twilio' in line:
            stats['test_tones'] += 1
        
        # Track OpenAI responses
        if 'response.audio.delta' in line or 'response.done' in line:
            stats['openai_responses'].append(line.strip()[:100])
    
    # Print analysis
    print("\n" + "="*60)
    print("AUDIO FLOW ANALYSIS")
    print("="*60)
    
    print("\n📊 TWILIO EVENTS:")
    for event, count in stats['twilio_events'].items():
        print(f"  - {event}: {count}")
    
    print(f"\n📥 AUDIO RECEIVED FROM TWILIO:")
    if stats['audio_received']:
        total_bytes = sum(stats['audio_received'])
        print(f"  - Total media events: {len(stats['audio_received'])}")
        print(f"  - Total bytes received: {total_bytes}")
        print(f"  - Average bytes per event: {total_bytes/len(stats['audio_received']):.1f}")
    else:
        print("  ❌ NO AUDIO RECEIVED!")
    
    print(f"\n🔇 FRAME ANALYSIS:")
    total_frames = stats['silent_frames'] + stats['non_silent_frames']
    if total_frames > 0:
        print(f"  - Silent frames: {stats['silent_frames']} ({stats['silent_frames']/total_frames*100:.1f}%)")
        print(f"  - Non-silent frames: {stats['non_silent_frames']} ({stats['non_silent_frames']/total_frames*100:.1f}%)")
    else:
        print("  ❌ NO FRAMES PROCESSED!")
    
    print(f"\n📤 AUDIO SENT TO OPENAI:")
    if stats['audio_sent_to_openai']:
        success_count = stats['audio_sent_to_openai'].count('success')
        failed_count = stats['audio_sent_to_openai'].count('failed')
        error_count = stats['audio_sent_to_openai'].count('error')
        print(f"  - Successful: {success_count}")
        print(f"  - Failed: {failed_count}")
        print(f"  - Errors: {error_count}")
    else:
        print("  ❌ NO AUDIO SENT TO OPENAI!")
    
    print(f"\n💾 OPENAI BUFFER STATE:")
    if stats['openai_buffer_state']:
        print(f"  - Buffer updates: {len(stats['openai_buffer_state'])}")
        print(f"  - Max buffered: {max(stats['openai_buffer_state']):.1f}ms")
        print(f"  - Min buffered: {min(stats['openai_buffer_state']):.1f}ms")
        # Show last 5 buffer states
        print(f"  - Last 5 states: {stats['openai_buffer_state'][-5:]}")
    else:
        print("  ❌ NO BUFFER STATE TRACKED!")
    
    print(f"\n✅ COMMITS:")
    if stats['commits']:
        print(f"  - Total commit attempts: {len(stats['commits'])}")
        # Show last 3 commits
        for commit in stats['commits'][-3:]:
            print(f"    {commit[:150]}")
    else:
        print("  ❌ NO COMMITS ATTEMPTED!")
    
    print(f"\n🔊 OTHER AUDIO:")
    print(f"  - Echo attempts: {stats['echo_attempts']}")
    print(f"  - Test tones sent: {stats['test_tones']}")
    
    print(f"\n⚠️ ERRORS:")
    print(f"  - Empty buffer errors: {stats['empty_buffer_errors']}")
    if stats['errors']:
        print(f"  - Total errors: {len(stats['errors'])}")
        # Show unique error types
        unique_errors = []
        for error in stats['errors'][-10:]:  # Last 10 errors
            if 'input_audio_buffer_commit_empty' in error:
                if 'input_audio_buffer_commit_empty' not in str(unique_errors):
                    unique_errors.append("input_audio_buffer_commit_empty error")
            elif error not in unique_errors:
                unique_errors.append(error[:100])
        
        for error in unique_errors[:5]:  # Show up to 5 unique errors
            print(f"    - {error}")
    
    print(f"\n🤖 OPENAI RESPONSES:")
    if stats['openai_responses']:
        print(f"  - Response events: {len(stats['openai_responses'])}")
    else:
        print("  ❌ NO OPENAI RESPONSES!")
    
    # Diagnosis
    print("\n" + "="*60)
    print("DIAGNOSIS:")
    print("="*60)
    
    if not stats['audio_received']:
        print("❌ CRITICAL: No audio received from Twilio!")
    elif stats['silent_frames'] > stats['non_silent_frames'] * 2:
        print("⚠️ WARNING: Mostly silent frames - microphone might be muted or not working")
    elif not stats['audio_sent_to_openai']:
        print("❌ CRITICAL: Audio received but not sent to OpenAI - processing issue")
    elif stats['empty_buffer_errors'] > 0:
        print(f"⚠️ WARNING: {stats['empty_buffer_errors']} empty buffer errors - audio not accumulating properly")
    elif not stats['commits']:
        print("❌ CRITICAL: No audio commits attempted - buffering issue")
    else:
        print("✅ Audio flow appears to be working")
    
    if total_frames == 0:
        print("❌ CRITICAL: No frames being processed from Twilio audio")
    
    if stats['openai_buffer_state'] and max(stats['openai_buffer_state']) < 100:
        print("⚠️ WARNING: OpenAI buffer never reaches 100ms minimum for commit")

if __name__ == "__main__":
    # Default to today's log file
    import glob
    import os
    
    # Find the most recent log file
    log_files = glob.glob("logs/*.log")
    if not log_files:
        print("No log files found in logs/ directory")
        sys.exit(1)
    
    # Get the most recent log file
    latest_log = max(log_files, key=os.path.getmtime)
    print(f"Analyzing: {latest_log}")
    
    analyze_logs(latest_log)
