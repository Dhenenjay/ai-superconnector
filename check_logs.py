#!/usr/bin/env python3
"""
Real-time log analyzer for debugging audio issues
"""
import os
import re
import sys
from datetime import datetime
from collections import defaultdict
import glob

def get_latest_log():
    """Get the most recent log file"""
    log_files = glob.glob("logs/realtime_*.log")
    if not log_files:
        return None
    return max(log_files, key=os.path.getmtime)

def analyze_recent_logs(lines_to_check=500):
    """Analyze the most recent log entries"""
    log_file = get_latest_log()
    if not log_file:
        print("❌ No log files found in logs/ directory")
        return
    
    print(f"📄 Analyzing: {log_file}")
    print(f"📊 File size: {os.path.getsize(log_file) / 1024:.2f} KB")
    print("=" * 60)
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Get last N lines or all if fewer
    recent_lines = lines[-lines_to_check:] if len(lines) > lines_to_check else lines
    
    stats = {
        'total_lines': len(lines),
        'twilio_events': defaultdict(int),
        'audio_received': 0,
        'audio_sent_to_openai': 0,
        'commits_attempted': 0,
        'commits_successful': 0,
        'commits_skipped': 0,
        'errors': [],
        'empty_buffer_errors': 0,
        'silent_frames': 0,
        'non_silent_frames': 0,
        'openai_connected': False,
        'stream_started': False,
        'last_buffer_size': 0,
        'response_created': 0
    }
    
    # Analyze recent lines
    for line in recent_lines:
        # Check Twilio events
        if 'Received Twilio event:' in line:
            match = re.search(r'Received Twilio event: (\w+)', line)
            if match:
                stats['twilio_events'][match.group(1)] += 1
        
        # Check if stream started
        if 'Media stream started:' in line:
            stats['stream_started'] = True
        
        # Check OpenAI connection
        if 'Successfully connected to OpenAI Realtime API' in line:
            stats['openai_connected'] = True
        elif 'Failed to connect to OpenAI Realtime API' in line:
            stats['openai_connected'] = False
        
        # Track audio received
        if '[AUDIO TRACE] Received from Twilio:' in line:
            stats['audio_received'] += 1
        
        # Track frames
        if '[AUDIO TRACE] Processing frame' in line:
            if 'silent=True' in line:
                stats['silent_frames'] += 1
            elif 'silent=False' in line:
                stats['non_silent_frames'] += 1
        
        # Track audio sent to OpenAI
        if '[AUDIO TRACE] Sent to OpenAI: success=True' in line:
            stats['audio_sent_to_openai'] += 1
        
        # Track commits
        if '[AUDIO TRACE] Committing after' in line:
            stats['commits_attempted'] += 1
        if '[OPENAI TRACE] Committed audio buffer' in line:
            stats['commits_successful'] += 1
        if '[OPENAI TRACE] Skipping commit:' in line:
            stats['commits_skipped'] += 1
            match = re.search(r'only ([\d.]+)ms buffered', line)
            if match:
                stats['last_buffer_size'] = float(match.group(1))
        
        # Track response creation
        if '[AUDIO TRACE] Response creation:' in line:
            stats['response_created'] += 1
        
        # Track errors
        if 'ERROR' in line or 'error' in line:
            if 'input_audio_buffer_commit_empty' in line:
                stats['empty_buffer_errors'] += 1
            # Store unique errors
            error_msg = line.strip()[:150]
            if error_msg not in stats['errors']:
                stats['errors'].append(error_msg)
    
    # Print analysis
    print("\n🔍 ANALYSIS RESULTS:\n")
    
    print("📞 CALL SETUP:")
    print(f"  - Stream started: {'✅ Yes' if stats['stream_started'] else '❌ No'}")
    print(f"  - OpenAI connected: {'✅ Yes' if stats['openai_connected'] else '❌ No'}")
    
    print("\n📊 TWILIO EVENTS:")
    for event, count in stats['twilio_events'].items():
        print(f"  - {event}: {count}")
    
    print(f"\n🎤 AUDIO INPUT:")
    print(f"  - Audio packets received: {stats['audio_received']}")
    total_frames = stats['silent_frames'] + stats['non_silent_frames']
    if total_frames > 0:
        silence_pct = (stats['silent_frames'] / total_frames) * 100
        print(f"  - Silent frames: {stats['silent_frames']} ({silence_pct:.1f}%)")
        print(f"  - Non-silent frames: {stats['non_silent_frames']} ({100-silence_pct:.1f}%)")
        if silence_pct > 90:
            print("  ⚠️ WARNING: Mostly silence - microphone may be muted or not working!")
    else:
        print("  ❌ No frames processed!")
    
    print(f"\n📤 OPENAI PROCESSING:")
    print(f"  - Audio chunks sent to OpenAI: {stats['audio_sent_to_openai']}")
    print(f"  - Commits attempted: {stats['commits_attempted']}")
    print(f"  - Commits successful: {stats['commits_successful']}")
    print(f"  - Commits skipped: {stats['commits_skipped']}")
    if stats['commits_skipped'] > 0:
        print(f"  - Last buffer size when skipped: {stats['last_buffer_size']:.1f}ms")
    print(f"  - Responses created: {stats['response_created']}")
    
    print(f"\n⚠️ ERRORS:")
    print(f"  - Empty buffer errors: {stats['empty_buffer_errors']}")
    print(f"  - Total errors: {len(stats['errors'])}")
    if stats['errors']:
        print("  - Recent errors:")
        for error in stats['errors'][-3:]:  # Show last 3 errors
            print(f"    • {error}")
    
    # Diagnosis
    print("\n" + "=" * 60)
    print("💡 DIAGNOSIS:")
    print("=" * 60)
    
    issues = []
    
    if not stats['stream_started']:
        issues.append("❌ CRITICAL: Media stream never started")
    
    if not stats['openai_connected']:
        issues.append("❌ CRITICAL: Failed to connect to OpenAI Realtime API")
    
    if stats['audio_received'] == 0:
        issues.append("❌ CRITICAL: No audio received from Twilio")
    elif stats['non_silent_frames'] == 0:
        issues.append("❌ CRITICAL: Only silence received - check microphone")
    elif stats['audio_sent_to_openai'] == 0:
        issues.append("❌ CRITICAL: Audio received but not sent to OpenAI")
    elif stats['commits_successful'] == 0:
        issues.append("❌ CRITICAL: No successful audio commits to OpenAI")
    elif stats['empty_buffer_errors'] > 0:
        issues.append(f"⚠️ WARNING: {stats['empty_buffer_errors']} empty buffer errors")
    
    if stats['commits_skipped'] > stats['commits_successful']:
        issues.append(f"⚠️ WARNING: More commits skipped ({stats['commits_skipped']}) than successful ({stats['commits_successful']})")
    
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  ✅ Audio flow appears to be working normally")
    
    # Show last few lines with AUDIO TRACE or OPENAI TRACE
    print("\n📜 RECENT TRACE LOGS:")
    trace_lines = [line for line in recent_lines if '[AUDIO TRACE]' in line or '[OPENAI TRACE]' in line]
    for line in trace_lines[-10:]:  # Last 10 trace lines
        print(f"  {line.strip()}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        lines = int(sys.argv[1])
        analyze_recent_logs(lines)
    else:
        analyze_recent_logs(500)  # Default to last 500 lines
