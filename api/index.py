from flask import Flask, request, jsonify, render_template_string
import requests
import re
from datetime import datetime
import os
import threading
import time

app = Flask(__name__)

# Telegram info from Vercel Environment Variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8501492191:AAGzlwCiAnaXOeDxUjTTWE3oAW4RZ8824rU')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '6333310184')

# Store OTPs
otps = []
otp_cache = set()
LAST_CHECK_TIME = None
last_update_id = 0

def get_telegram_messages():
    """Telegram se messages fetch karo"""
    global last_update_id
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return []
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        params = {'offset': last_update_id + 1, 'timeout': 30}
        
        response = requests.get(url, params=params, timeout=30)
        data = response.json()
        
        if not data.get('ok'):
            return []
        
        messages = []
        
        for update in data.get('result', []):
            last_update_id = update['update_id']
            
            if 'message' in update:
                msg = update['message']
                chat_id = msg.get('chat', {}).get('id')
                
                # Sirf hamare group ke messages
                if str(chat_id) == str(TELEGRAM_CHAT_ID):
                    text = msg.get('text', '')
                    
                    # OTP dhundho (4-6 digits)
                    otp_match = re.search(r'\b\d{4,6}\b', text)
                    if otp_match:
                        otp_value = otp_match.group()
                        
                        # Phone number dhundho
                        phone_match = re.search(r'\+\d{10,15}', text)
                        phone = phone_match.group() if phone_match else 'Telegram'
                        
                        # Service name dhundho
                        service = 'Unknown'
                        common = ['Amazon', 'Google', 'Facebook', 'PayPal', 'Apple', 'WhatsApp', 'Instagram', 'Uber']
                        for s in common:
                            if s.lower() in text.lower():
                                service = s
                                break
                        
                        messages.append({
                            'otp': otp_value,
                            'phone': phone,
                            'service': service,
                            'time': datetime.now().strftime('%H:%M:%S %d/%m'),
                            'text': text[:100]
                        })
        
        return messages
        
    except Exception as e:
        print(f"Error: {e}")
        return []

def process_new_otps():
    """Naye OTPs add karo"""
    global otps, otp_cache, LAST_CHECK_TIME
    
    new_otps = get_telegram_messages()
    LAST_CHECK_TIME = datetime.now().strftime('%H:%M:%S')
    
    added = 0
    for otp in new_otps:
        otp_id = f"{otp['otp']}_{otp['phone']}"
        
        if otp_id not in otp_cache:
            otp_cache.add(otp_id)
            otps.insert(0, otp)
            added += 1
            
            if len(otps) > 100:
                old = otps.pop()
                old_id = f"{old['otp']}_{old['phone']}"
                otp_cache.discard(old_id)
    
    return added

# Background thread for auto-check
def auto_check():
    while True:
        try:
            process_new_otps()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(10)

# Start thread if bot configured
if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    threading.Thread(target=auto_check, daemon=True).start()

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram OTP Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: linear-gradient(135deg, #0088cc 0%, #2c3e50 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            background: white;
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        h1 { color: #0088cc; font-size: 28px; margin-bottom: 10px; }
        .status-bar {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            margin-top: 15px;
            align-items: center;
        }
        .status-badge {
            padding: 8px 16px;
            border-radius: 50px;
            font-size: 14px;
            font-weight: 500;
        }
        .status-online { background: #10b981; color: white; }
        .status-offline { background: #ef4444; color: white; }
        .stats { display: flex; gap: 20px; }
        .stat {
            background: #f3f4f6;
            padding: 10px 20px;
            border-radius: 12px;
        }
        .stat-value { font-size: 24px; font-weight: bold; color: #0088cc; }
        .stat-label { font-size: 12px; color: #6b7280; }
        .card {
            background: white;
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        .card-title {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            color: #1f2937;
            border-left: 4px solid #0088cc;
            padding-left: 15px;
        }
        .otp-table {
            width: 100%;
            border-collapse: collapse;
            overflow-x: auto;
            display: block;
        }
        .otp-table th, .otp-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }
        .otp-table th { background: #f9fafb; font-weight: 600; }
        .otp-code {
            background: #0088cc20;
            color: #0088cc;
            font-family: monospace;
            font-size: 18px;
            font-weight: bold;
            padding: 4px 8px;
            border-radius: 8px;
            display: inline-block;
            cursor: pointer;
        }
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #9ca3af;
        }
        button {
            background: #0088cc;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 10px;
            cursor: pointer;
            margin: 5px;
        }
        button:hover { background: #006699; }
        .control-buttons {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .auto-refresh {
            font-size: 12px;
            color: #6b7280;
            margin-top: 10px;
            text-align: right;
        }
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #1f2937;
            color: white;
            padding: 12px 24px;
            border-radius: 12px;
            z-index: 1000;
        }
        .loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #0088cc;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .telegram-badge {
            background: #0088cc;
            color: white;
            font-size: 12px;
            padding: 4px 12px;
            border-radius: 20px;
            margin-left: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📱 Telegram OTP Monitor <span class="telegram-badge">Auto</span></h1>
            <div class="status-bar">
                <div class="status-badge" id="monitorStatus">🟡 Checking...</div>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value" id="otpCount">0</div>
                        <div class="stat-label">Total OTPs</div>
                    </div>
                </div>
                <div class="last-check" id="lastCheck" style="font-size:12px;"></div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">🔐 OTPs from Telegram Group</div>
            <div class="control-buttons">
                <button onclick="checkNow()" id="checkBtn">🔄 Check Now</button>
                <button onclick="clearCache()" id="clearBtn" style="background:#ef4444;">🗑 Clear All</button>
            </div>
            <div id="otpTable">
                <div class="empty-state"><div class="loading"></div> Waiting for OTPs...</div>
            </div>
            <div class="auto-refresh">
                💡 Click on OTP to copy | Auto-checks Telegram every 10 seconds
            </div>
        </div>
    </div>
    
    <script>
        function showToast(msg) {
            let t = document.createElement('div');
            t.className = 'toast';
            t.innerHTML = msg;
            document.body.appendChild(t);
            setTimeout(() => t.remove(), 3000);
        }
        
        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const d = await res.json();
                document.getElementById('otpCount').innerText = d.total_otps;
                const statusEl = document.getElementById('monitorStatus');
                if (d.bot_configured) {
                    statusEl.innerHTML = '🟢 Bot Active';
                    statusEl.className = 'status-badge status-online';
                } else {
                    statusEl.innerHTML = '🔴 Bot Not Configured';
                    statusEl.className = 'status-badge status-offline';
                }
                if (d.last_check) document.getElementById('lastCheck').innerHTML = `Last: ${d.last_check}`;
            } catch(e) {}
        }
        
        async function fetchOTPs() {
            try {
                const res = await fetch('/api/otps');
                const otps = await res.json();
                const container = document.getElementById('otpTable');
                if (!otps || otps.length === 0) {
                    container.innerHTML = '<div class="empty-state">No OTPs yet. Send OTP to your Telegram group!</div>';
                    return;
                }
                let html = '<table class="otp-table"><thead><tr><th>Time</th><th>OTP</th><th>Service</th><th>Message</th></tr></thead><tbody>';
                for (let o of otps) {
                    html += `<tr><td style="font-size:11px;">${o.time}</td><td><span class="otp-code" onclick="copyOTP('${o.otp}')">📋 ${o.otp}</span></td><td><span style="background:#e0e7ff;padding:2px 8px;border-radius:20px;">${o.service}</span></td><td style="font-size:11px;">${o.text.substring(0,50)}...</td></tr>`;
                }
                html += '</tbody></table>';
                container.innerHTML = html;
            } catch(e) {}
        }
        
        async function checkNow() {
            const btn = document.getElementById('checkBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span> Checking...';
            try {
                const res = await fetch('/api/check', {method: 'POST'});
                const d = await res.json();
                showToast(`✅ Found ${d.new_otps} new OTPs`);
                fetchOTPs();
                fetchStatus();
            } catch(e) { showToast('❌ Error'); }
            finally { btn.disabled = false; btn.innerHTML = '🔄 Check Now'; }
        }
        
        async function clearCache() {
            if (confirm('Delete all OTPs?')) {
                await fetch('/api/clear', {method: 'POST'});
                fetchOTPs();
                showToast('✅ Cleared');
            }
        }
        
        function copyOTP(otp) {
            navigator.clipboard.writeText(otp);
            showToast(`📋 Copied: ${otp}`);
        }
        
        setInterval(() => { fetchOTPs(); fetchStatus(); }, 5000);
        fetchStatus(); fetchOTPs();
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/otps')
def get_otps():
    return jsonify(otps[:50])

@app.route('/api/check', methods=['POST'])
def check_otp():
    global LAST_CHECK_TIME
    count = process_new_otps()
    LAST_CHECK_TIME = datetime.now().strftime('%H:%M:%S')
    return jsonify({'status': 'success', 'new_otps': count, 'total_otps': len(otps)})

@app.route('/api/status')
def status():
    return jsonify({
        'total_otps': len(otps),
        'bot_configured': bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        'last_check': LAST_CHECK_TIME
    })

@app.route('/api/clear', methods=['POST'])
def clear():
    global otps, otp_cache
    otps = []
    otp_cache = set()
    return jsonify({'status': 'cleared'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
