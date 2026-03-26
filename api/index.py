from flask import Flask, request, jsonify, render_template_string
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import threading

app = Flask(__name__)

# iVASMS credentials from environment variables
IVASMS_EMAIL = os.environ.get('IVASMS_EMAIL', '')
IVASMS_PASSWORD = os.environ.get('IVASMS_PASSWORD', '')
SESSION_COOKIE = None
LAST_LOGIN_TIME = None
LOGIN_STATUS = False

# Store data
otps = []
numbers = []
otp_cache = set()
LAST_CHECK_TIME = None

# Auto-refresh login ka timer
AUTO_REFRESH_ACTIVE = True

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>iVASMS OTP Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            background: white;
            border-radius: 20px;
            padding: 25px 30px;
            margin-bottom: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        h1 { color: #667eea; font-size: 28px; margin-bottom: 10px; }
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
        .status-warning { background: #f59e0b; color: white; }
        .status-refresh { background: #3b82f6; color: white; animation: pulse 1s infinite; }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
        .stats { display: flex; gap: 20px; flex-wrap: wrap; }
        .stat {
            background: #f3f4f6;
            padding: 10px 20px;
            border-radius: 12px;
        }
        .stat-value { font-size: 24px; font-weight: bold; color: #667eea; }
        .stat-label { font-size: 12px; color: #6b7280; }
        .grid {
            display: grid;
            grid-template-columns: 1fr 1.5fr;
            gap: 25px;
        }
        @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
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
            border-left: 4px solid #667eea;
            padding-left: 15px;
        }
        .numbers-list {
            max-height: 400px;
            overflow-y: auto;
        }
        .number-item {
            background: #f9fafb;
            padding: 12px 15px;
            border-radius: 12px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-family: monospace;
        }
        .add-number-form {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        .add-number-form input {
            flex: 1;
            padding: 12px 15px;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            font-size: 14px;
            outline: none;
            min-width: 150px;
        }
        .add-number-form input:focus { border-color: #667eea; }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 12px;
            cursor: pointer;
            font-weight: 500;
            transition: transform 0.2s;
        }
        button:hover { background: #5a67d8; transform: translateY(-2px); }
        button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
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
            background: #667eea20;
            color: #667eea;
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
        .control-buttons {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .btn-success { background: #10b981; }
        .btn-success:hover { background: #059669; }
        .btn-warning { background: #f59e0b; }
        .btn-warning:hover { background: #d97706; }
        .btn-secondary { background: #6b7280; }
        .auto-refresh { font-size: 12px; color: #6b7280; margin-top: 10px; text-align: right; }
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #1f2937;
            color: white;
            padding: 12px 24px;
            border-radius: 12px;
            z-index: 1000;
            animation: slideIn 0.3s ease;
        }
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .auto-badge {
            background: #e0e7ff;
            color: #4338ca;
            font-size: 10px;
            padding: 4px 8px;
            border-radius: 20px;
            margin-left: 10px;
        }
        @media (max-width: 600px) {
            .otp-table th, .otp-table td {
                padding: 8px;
                font-size: 12px;
            }
            .otp-code { font-size: 14px; }
            button { padding: 8px 16px; font-size: 12px; }
            .card { padding: 15px; }
            .header { padding: 15px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📱 iVASMS OTP Monitor <span class="auto-badge">🤖 Auto-Login Active</span></h1>
            <div class="status-bar">
                <div class="status-badge" id="monitorStatus">🟡 Checking...</div>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value" id="otpCount">0</div>
                        <div class="stat-label">Total OTPs</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value" id="numberCount">0</div>
                        <div class="stat-label">Saved Numbers</div>
                    </div>
                </div>
                <div class="last-check" id="lastCheck" style="font-size:12px;color:#6b7280;"></div>
            </div>
            <div style="font-size:11px; color:#6b7280; margin-top:10px;">
                🔄 Auto-Login: Session expire hone par khud ba khud refresh ho jayega
            </div>
        </div>
        
        <div class="grid">
            <div class="card">
                <div class="card-title">📞 Numbers List</div>
                <div class="control-buttons">
                    <button onclick="checkNow()" id="checkBtn" class="btn-success">🔄 Check OTPs</button>
                    <button onclick="clearCache()" id="clearBtn" class="btn-warning">🗑 Clear All</button>
                </div>
                <div class="numbers-list" id="numbersList">
                    <div class="empty-state">No numbers added yet. Add one below!</div>
                </div>
                <div class="add-number-form">
                    <input type="text" id="numberInput" placeholder="+923001234567" autocomplete="off">
                    <button onclick="addNumber()">➕ Add Number</button>
                </div>
                <div class="auto-refresh" style="margin-top: 10px;">
                    💡 Add numbers for reference. OTPs from all numbers will appear.
                </div>
            </div>
            
            <div class="card">
                <div class="card-title">🔐 Received OTPs</div>
                <div id="otpTable">
                    <div class="empty-state">
                        <div class="loading"></div> Loading OTPs...
                    </div>
                </div>
                <div class="auto-refresh">
                    🔄 Click on OTP to copy | Login auto-refreshes every 10 minutes
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function showToast(message) {
            let toast = document.createElement('div');
            toast.className = 'toast';
            toast.innerHTML = message;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }
        
        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                document.getElementById('otpCount').innerText = data.total_otps;
                document.getElementById('numberCount').innerText = data.total_numbers;
                
                const statusEl = document.getElementById('monitorStatus');
                if (data.logged_in) {
                    statusEl.innerHTML = '🟢 iVASMS Connected (Auto-Refresh)';
                    statusEl.className = 'status-badge status-online';
                } else {
                    statusEl.innerHTML = '🟡 Auto-Login Attempting...';
                    statusEl.className = 'status-badge status-refresh';
                }
                
                if (data.last_check) {
                    document.getElementById('lastCheck').innerHTML = `Last check: ${data.last_check}`;
                }
                if (data.last_login) {
                    document.getElementById('lastCheck').innerHTML += ` | Login: ${data.last_login}`;
                }
            } catch(e) {
                console.error('Status fetch error:', e);
            }
        }
        
        async function fetchOTPs() {
            try {
                const res = await fetch('/api/otps');
                const otps = await res.json();
                updateOTPTable(otps);
            } catch(e) {
                console.error('OTP fetch error:', e);
            }
        }
        
        async function fetchNumbers() {
            try {
                const res = await fetch('/api/numbers');
                const numbers = await res.json();
                updateNumbersList(numbers);
            } catch(e) {
                console.error('Numbers fetch error:', e);
            }
        }
        
        function updateOTPTable(otps) {
            const container = document.getElementById('otpTable');
            
            if (!otps || otps.length === 0) {
                container.innerHTML = '<div class="empty-state">📭 No OTPs yet. Click "Check OTPs" to fetch from iVASMS!</div>';
                return;
            }
            
            let html = `<div style="overflow-x: auto;"><table class="otp-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>OTP</th>
                        <th>Phone</th>
                        <th>Service</th>
                    </tr>
                </thead>
                <tbody>`;
            
            for (let otp of otps) {
                html += `<tr>
                    <td style="font-size: 12px;">${otp.time}</td>
                    <td><span class="otp-code" onclick="copyOTP('${otp.otp}')">📋 ${otp.otp}</span></td>
                    <td><code>${otp.phone}</code></td>
                    <td>${otp.service}</td>
                </tr>`;
            }
            
            html += `</tbody>
            </table></div>`;
            container.innerHTML = html;
        }
        
        function updateNumbersList(numbers) {
            const container = document.getElementById('numbersList');
            
            if (!numbers || numbers.length === 0) {
                container.innerHTML = '<div class="empty-state">📞 No numbers added yet. Add one below!</div>';
                return;
            }
            
            let html = '';
            for (let number of numbers) {
                html += `<div class="number-item">
                    <code>${number}</code>
                    <button class="delete-btn" style="background:#ef4444;padding:5px 12px;" onclick="removeNumber('${number}')">Remove</button>
                </div>`;
            }
            container.innerHTML = html;
        }
        
        async function addNumber() {
            const input = document.getElementById('numberInput');
            const number = input.value.trim();
            
            if (!number) {
                showToast('Please enter a number');
                return;
            }
            
            try {
                const res = await fetch('/api/numbers', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({number: number})
                });
                const data = await res.json();
                
                if (data.status === 'added') {
                    input.value = '';
                    fetchNumbers();
                    showToast(`✅ Added ${number}`);
                } else {
                    showToast(data.message || 'Error adding number');
                }
            } catch(e) {
                showToast('Error adding number');
            }
        }
        
        async function removeNumber(number) {
            try {
                const res = await fetch('/api/numbers', {
                    method: 'DELETE',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({number: number})
                });
                const data = await res.json();
                
                if (data.status === 'removed') {
                    fetchNumbers();
                    showToast(`✅ Removed ${number}`);
                }
            } catch(e) {
                showToast('Error removing number');
            }
        }
        
        async function checkNow() {
            const btn = document.getElementById('checkBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span> Fetching OTPs...';
            
            try {
                const res = await fetch('/api/check', {method: 'POST'});
                const data = await res.json();
                if (data.status === 'success') {
                    showToast(`✅ Found ${data.new_otps} new OTPs! Total: ${data.total_otps}`);
                } else {
                    showToast(`❌ ${data.message}`);
                }
                fetchOTPs();
                fetchStatus();
            } catch(e) {
                showToast('❌ Error checking OTPs');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '🔄 Check OTPs';
            }
        }
        
        async function clearCache() {
            if (confirm('⚠️ Are you sure? This will delete all OTPs.')) {
                const btn = document.getElementById('clearBtn');
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> Clearing...';
                
                try {
                    await fetch('/api/clear', {method: 'POST'});
                    fetchOTPs();
                    fetchStatus();
                    showToast('✅ All OTPs cleared!');
                } catch(e) {
                    showToast('❌ Error clearing cache');
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = '🗑 Clear All';
                }
            }
        }
        
        function copyOTP(otp) {
            navigator.clipboard.writeText(otp);
            showToast(`📋 Copied: ${otp}`);
        }
        
        // Auto-refresh every 15 seconds
        setInterval(() => {
            fetchOTPs();
            fetchNumbers();
            fetchStatus();
        }, 15000);
        
        // Initial load
        fetchStatus();
        fetchOTPs();
        fetchNumbers();
    </script>
</body>
</html>
"""

def login_ivasms():
    """Login to iVASMS and get session cookie"""
    global SESSION_COOKIE, LAST_LOGIN_TIME, LOGIN_STATUS
    
    if not IVASMS_EMAIL or not IVASMS_PASSWORD:
        LOGIN_STATUS = False
        return False
    
    try:
        session = requests.Session()
        
        # Get login page first
        login_page = session.get('https://ivasms.com/login', timeout=30)
        soup = BeautifulSoup(login_page.text, 'html.parser')
        
        # Find CSRF token if exists
        csrf_token = None
        token_input = soup.find('input', {'name': 'csrf_token'})
        if token_input:
            csrf_token = token_input.get('value')
        
        # Login data
        login_data = {
            'email': IVASMS_EMAIL,
            'password': IVASMS_PASSWORD
        }
        if csrf_token:
            login_data['csrf_token'] = csrf_token
        
        # Post login
        response = session.post('https://ivasms.com/login', data=login_data, timeout=30)
        
        # Check if login successful
        if 'dashboard' in response.url or 'sms' in response.url or response.status_code == 200:
            SESSION_COOKIE = session.cookies.get_dict()
            LAST_LOGIN_TIME = datetime.now().strftime('%H:%M:%S %d/%m')
            LOGIN_STATUS = True
            print(f"✅ Login successful at {LAST_LOGIN_TIME}")
            return True
        else:
            LOGIN_STATUS = False
            print("❌ Login failed")
            return False
            
    except Exception as e:
        print(f"Login error: {e}")
        LOGIN_STATUS = False
        return False

def get_otps_from_ivasms():
    """Fetch OTPs from iVASMS"""
    global SESSION_COOKIE, LOGIN_STATUS
    
    if not SESSION_COOKIE or not LOGIN_STATUS:
        if not login_ivasms():
            return []
    
    try:
        session = requests.Session()
        session.cookies.update(SESSION_COOKIE)
        
        # Try to get SMS page
        response = session.get('https://ivasms.com/sms', timeout=30)
        
        if response.status_code != 200:
            # Try alternative URLs
            response = session.get('https://ivasms.com/dashboard', timeout=30)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try different selectors for SMS messages
        messages = []
        selectors = [
            'div.sms-message',
            'div.message',
            'li.sms-item',
            'div.msg-item',
            'div.message-content'
        ]
        
        for selector in selectors:
            found = soup.select(selector)
            if found:
                messages = found
                break
        
        if not messages:
            # Look for any element containing OTP pattern
            all_elements = soup.find_all(['div', 'li', 'p', 'span', 'td'])
            for elem in all_elements:
                text = elem.get_text()
                if re.search(r'\b\d{4,6}\b', text) and len(text) < 300:
                    messages.append(elem)
        
        otps_found = []
        
        for msg in messages:
            text = msg.get_text()
            
            # Extract OTP (4-6 digit numbers)
            otp_match = re.search(r'\b\d{4,6}\b', text)
            if otp_match:
                otp_value = otp_match.group()
                
                # Extract phone number if present
                phone_match = re.search(r'\+\d{10,15}', text)
                phone = phone_match.group() if phone_match else 'Unknown'
                
                # Extract service name
                service = 'Unknown'
                service_match = re.search(r'([A-Za-z0-9]+)\s*:', text)
                if service_match:
                    service = service_match.group(1)
                else:
                    common_services = ['Amazon', 'Google', 'Facebook', 'PayPal', 'Apple', 'Microsoft', 'WhatsApp', 'Instagram', 'Uber', 'Netflix']
                    for s in common_services:
                        if s.lower() in text.lower():
                            service = s
                            break
                
                otps_found.append({
                    'otp': otp_value,
                    'text': text[:200],
                    'phone': phone,
                    'service': service,
                    'time': datetime.now().strftime('%H:%M:%S %d/%m/%Y')
                })
        
        return otps_found
        
    except Exception as e:
        print(f"Fetch error: {e}")
        # Session might be expired, trigger re-login
        LOGIN_STATUS = False
        SESSION_COOKIE = None
        return []

# Auto-refresh login function that runs in background
def auto_refresh_login():
    """Background thread to keep login alive"""
    global LOGIN_STATUS
    while True:
        time.sleep(600)  # Check every 10 minutes
        print("🔄 Auto-refreshing login...")
        if login_ivasms():
            print("✅ Login auto-refreshed successfully")
        else:
            print("❌ Auto-refresh login failed, will retry in 10 minutes")

# Start auto-refresh thread
if IVASMS_EMAIL and IVASMS_PASSWORD:
    refresh_thread = threading.Thread(target=auto_refresh_login, daemon=True)
    refresh_thread.start()
    # Also do initial login
    login_ivasms()

LAST_CHECK_TIME = None

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/otps')
def get_otps():
    return jsonify(otps[:50])

@app.route('/api/numbers', methods=['GET', 'POST', 'DELETE'])
def manage_numbers():
    global numbers
    
    if request.method == 'POST':
        data = request.get_json()
        number = data.get('number')
        if number and number not in numbers:
            numbers.append(number)
            return jsonify({'status': 'added', 'number': number})
        return jsonify({'status': 'error', 'message': 'Number exists or invalid'})
    
    elif request.method == 'DELETE':
        data = request.get_json()
        number = data.get('number')
        if number and number in numbers:
            numbers.remove(number)
            return jsonify({'status': 'removed', 'number': number})
    
    return jsonify(numbers)

@app.route('/api/check', methods=['POST'])
def check_otp():
    global otps, otp_cache, LAST_CHECK_TIME, LOGIN_STATUS
    
    if not IVASMS_EMAIL or not IVASMS_PASSWORD:
        return jsonify({
            'status': 'error',
            'message': 'iVASMS credentials not configured. Add IVASMS_EMAIL and IVASMS_PASSWORD in Environment Variables.'
        })
    
    # Check login status and refresh if needed
    if not LOGIN_STATUS:
        login_ivasms()
    
    new_otps = get_otps_from_ivasms()
    LAST_CHECK_TIME = datetime.now().strftime('%H:%M:%S')
    
    added_count = 0
    for otp in new_otps:
        otp_id = f"{otp['otp']}_{otp['phone']}"
        
        if otp_id not in otp_cache:
            otp_cache.add(otp_id)
            otp['id'] = len(otps)
            otps.insert(0, otp)
            added_count += 1
            
            if len(otps) > 100:
                old = otps.pop()
                old_id = f"{old['otp']}_{old['phone']}"
                if old_id in otp_cache:
                    otp_cache.remove(old_id)
    
    return jsonify({
        'status': 'success',
        'new_otps': added_count,
        'total_otps': len(otps),
        'last_check': LAST_CHECK_TIME
    })

@app.route('/api/status')
def status():
    return jsonify({
        'total_otps': len(otps),
        'total_numbers': len(numbers),
        'ivasms_configured': bool(IVASMS_EMAIL and IVASMS_PASSWORD),
        'logged_in': LOGIN_STATUS,
        'last_check': LAST_CHECK_TIME,
        'last_login': LAST_LOGIN_TIME
    })

@app.route('/api/clear', methods=['POST'])
def clear():
    global otps, otp_cache
    otps = []
    otp_cache = set()
    return jsonify({'status': 'cleared'})

# For local testing
if __name__ == '__main__':
    app.run(debug=True, port=5000)
