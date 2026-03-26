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
IVASMS_EMAIL = os.environ.get('IVASMS_EMAIL', 'deedaralee17@gmail.com')
IVASMS_PASSWORD = os.environ.get('IVASMS_PASSWORD', 'Mallah123+')
SESSION_COOKIE = None
LAST_LOGIN_TIME = None
LOGIN_STATUS = False

# Store data
otps = []
numbers_list = []
otp_cache = set()
LAST_CHECK_TIME = None
LAST_NUMBERS_SYNC = None

# HTML Template (Clean version without duplicate times)
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
        .container { max-width: 1400px; margin: 0 auto; }
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
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }
        .sync-badge {
            background: #10b981;
            color: white;
            font-size: 12px;
            padding: 4px 12px;
            border-radius: 20px;
        }
        .numbers-list {
            max-height: 500px;
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
            font-size: 14px;
        }
        .number-item:hover {
            background: #f3f4f6;
        }
        .country-badge {
            background: #e0e7ff;
            color: #4338ca;
            font-size: 10px;
            padding: 2px 8px;
            border-radius: 20px;
            margin-left: 10px;
        }
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
        .info-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #e5e7eb;
            font-size: 12px;
            color: #6b7280;
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
            <h1>📱 iVASMS OTP Monitor <span class="auto-badge">🤖 Auto-Sync Active</span></h1>
            <div class="status-bar">
                <div class="status-badge" id="monitorStatus">🟡 Checking...</div>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value" id="otpCount">0</div>
                        <div class="stat-label">Total OTPs</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value" id="numberCount">0</div>
                        <div class="stat-label">Numbers from iVASMS</div>
                    </div>
                </div>
            </div>
            <div class="info-row">
                <span>🔄 Last OTP Check: <span id="lastCheck">--:--:--</span></span>
                <span>📞 Last Numbers Sync: <span id="lastSync">--:--:--</span></span>
                <span>🔐 Last Login: <span id="lastLogin">--:--:--</span></span>
            </div>
        </div>
        
        <div class="grid">
            <div class="card">
                <div class="card-title">
                    <span>📞 Numbers from iVASMS <span id="numberCountBadge"></span></span>
                    <span class="sync-badge">🔄 Auto-Sync (30 min)</span>
                </div>
                <div class="control-buttons">
                    <button onclick="checkNow()" id="checkBtn" class="btn-success">🔄 Check OTPs</button>
                    <button onclick="syncNumbersNow()" id="syncBtn" class="btn-secondary">📞 Sync Numbers Now</button>
                    <button onclick="clearCache()" id="clearBtn" class="btn-warning">🗑 Clear OTPs</button>
                </div>
                <div class="numbers-list" id="numbersList">
                    <div class="empty-state">
                        <div class="loading"></div> Loading numbers from iVASMS...
                    </div>
                </div>
                <div class="auto-refresh">
                    💡 Numbers automatically sync from iVASMS "My Numbers" every 30 minutes
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
                    🔄 Click on OTP to copy | Auto-sync every 30 min | Auto-login every 10 min
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
                
                if (data.last_check) {
                    document.getElementById('lastCheck').innerHTML = data.last_check;
                }
                if (data.last_numbers_sync) {
                    document.getElementById('lastSync').innerHTML = data.last_numbers_sync;
                }
                if (data.last_login) {
                    document.getElementById('lastLogin').innerHTML = data.last_login;
                }
                
                const statusEl = document.getElementById('monitorStatus');
                if (data.logged_in) {
                    statusEl.innerHTML = '🟢 iVASMS Connected (Auto-Sync)';
                    statusEl.className = 'status-badge status-online';
                } else {
                    statusEl.innerHTML = '🟡 Connecting to iVASMS...';
                    statusEl.className = 'status-badge status-warning';
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
                document.getElementById('numberCountBadge').innerHTML = `(${numbers.length} numbers)`;
            } catch(e) {
                console.error('Numbers fetch error:', e);
            }
        }
        
        async function syncNumbersNow() {
            const btn = document.getElementById('syncBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span> Syncing...';
            
            try {
                const res = await fetch('/api/sync-numbers', {method: 'POST'});
                const data = await res.json();
                if (data.status === 'success') {
                    showToast(`✅ Synced ${data.total_numbers} numbers from iVASMS`);
                    fetchNumbers();
                    fetchStatus();
                } else {
                    showToast(`❌ ${data.message}`);
                }
            } catch(e) {
                showToast('❌ Error syncing numbers');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '📞 Sync Numbers Now';
            }
        }
        
        function updateOTPTable(otps) {
            const container = document.getElementById('otpTable');
            
            if (!otps || otps.length === 0) {
                container.innerHTML = '<div class="empty-state">📭 No OTPs yet. Click "Check OTPs" to fetch!</div>';
                return;
            }
            
            let html = `<div style="overflow-x: auto;"><table class="otp-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>OTP</th>
                        <th>Phone</th>
                        <th>Service</th>
                    </thead>
                <tbody>`;
            
            for (let otp of otps) {
                html += `——
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
                container.innerHTML = '<div class="empty-state">📞 No numbers found in iVASMS. Click "Sync Numbers Now" to fetch!</div>';
                return;
            }
            
            let html = '';
            for (let item of numbers) {
                let flag = '📱';
                let number = item.number;
                
                if (number.startsWith('+213')) flag = '🇩🇿';
                else if (number.startsWith('+92')) flag = '🇵🇰';
                else if (number.startsWith('+966')) flag = '🇸🇦';
                else if (number.startsWith('+1')) flag = '🇺🇸';
                else if (number.startsWith('+44')) flag = '🇬🇧';
                
                html += `<div class="number-item">
                    <div>
                        <span style="font-size:18px; margin-right:10px;">${flag}</span>
                        <code style="font-size:14px;">${number}</code>
                    </div>
                    <div style="font-size:11px; color:#10b981;">✓ Active</div>
                </div>`;
            }
            container.innerHTML = html;
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
                    btn.innerHTML = '🗑 Clear OTPs';
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
    """Login to iVASMS"""
    global SESSION_COOKIE, LAST_LOGIN_TIME, LOGIN_STATUS
    
    if not IVASMS_EMAIL or not IVASMS_PASSWORD:
        LOGIN_STATUS = False
        return False
    
    try:
        session = requests.Session()
        
        # Get login page
        login_page = session.get('https://ivasms.com/login', timeout=30)
        soup = BeautifulSoup(login_page.text, 'html.parser')
        
        # Find CSRF token
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
        
        if response.status_code == 200:
            SESSION_COOKIE = session.cookies.get_dict()
            LAST_LOGIN_TIME = datetime.now().strftime('%H:%M:%S')
            LOGIN_STATUS = True
            print(f"✅ Login successful")
            return True
        else:
            LOGIN_STATUS = False
            return False
            
    except Exception as e:
        print(f"Login error: {e}")
        LOGIN_STATUS = False
        return False

def get_numbers_from_ivasms():
    """Fetch numbers from iVASMS My Numbers page"""
    global SESSION_COOKIE, LOGIN_STATUS
    
    if not SESSION_COOKIE or not LOGIN_STATUS:
        if not login_ivasms():
            return []
    
    try:
        session = requests.Session()
        session.cookies.update(SESSION_COOKIE)
        
        # Get the My Numbers page
        response = session.get('https://www.ivasms.com/portal/live/my_sms', timeout=30)
        
        if response.status_code != 200:
            response = session.get('https://ivasms.com/numbers', timeout=30)
        
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all phone numbers - look for pattern 2137xxxxx or 923xxxxx
        page_text = response.text
        
        # Pattern for Algeria numbers (2137...)
        algeria_pattern = r'2137\d{8}'
        # Pattern for Pakistan numbers (923...)
        pakistan_pattern = r'923\d{9}'
        
        numbers_found = []
        
        # Find all Algeria numbers
        algeria_matches = re.findall(algeria_pattern, page_text)
        for num in algeria_matches:
            formatted = '+' + num
            if formatted not in [n['number'] for n in numbers_found]:
                numbers_found.append({
                    'number': formatted,
                    'country': 'Algeria'
                })
        
        # Find all Pakistan numbers
        pakistan_matches = re.findall(pakistan_pattern, page_text)
        for num in pakistan_matches:
            formatted = '+' + num
            if formatted not in [n['number'] for n in numbers_found]:
                numbers_found.append({
                    'number': formatted,
                    'country': 'Pakistan'
                })
        
        # Also look for numbers in divs with specific classes
        number_divs = soup.find_all(['div', 'li', 'span'], class_=re.compile(r'number|phone|num', re.I))
        for div in number_divs:
            text = div.get_text()
            # Find any 10-15 digit numbers
            numbers_in_text = re.findall(r'\b\d{10,15}\b', text)
            for num in numbers_in_text:
                if num.startswith('2137') or num.startswith('923'):
                    formatted = '+' + num
                    if formatted not in [n['number'] for n in numbers_found]:
                        country = 'Algeria' if num.startswith('2137') else 'Pakistan' if num.startswith('923') else 'Unknown'
                        numbers_found.append({
                            'number': formatted,
                            'country': country
                        })
        
        # Also look for numbers in list items
        list_items = soup.find_all('li')
        for li in list_items:
            text = li.get_text()
            # Check for numbers in format like "213770660009"
            clean_text = text.strip()
            if re.match(r'^2137\d{8}$', clean_text):
                formatted = '+' + clean_text
                if formatted not in [n['number'] for n in numbers_found]:
                    numbers_found.append({
                        'number': formatted,
                        'country': 'Algeria'
                    })
            elif re.match(r'^923\d{9}$', clean_text):
                formatted = '+' + clean_text
                if formatted not in [n['number'] for n in numbers_found]:
                    numbers_found.append({
                        'number': formatted,
                        'country': 'Pakistan'
                    })
        
        print(f"✅ Found {len(numbers_found)} numbers from iVASMS")
        return numbers_found
        
    except Exception as e:
        print(f"Fetch numbers error: {e}")
        return []

def get_otps_from_ivasms():
    """Fetch OTPs from iVASMS"""
    global SESSION_COOKIE, LOGIN_STATUS
    
    if not SESSION_COOKIE or not LOGIN_STATUS:
        if not login_ivasms():
            return []
    
    try:
        session = requests.Session()
        session.cookies.update(SESSION_COOKIE)
        
        response = session.get('https://ivasms.com/sms', timeout=30)
        
        if response.status_code != 200:
            response = session.get('https://ivasms.com/dashboard', timeout=30)
        
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find SMS messages
        messages = []
        
        # Try different selectors
        for selector in ['div.sms-message', 'div.message', 'li.sms-item', 'div.msg-item', '.message-content']:
            found = soup.select(selector)
            if found:
                messages = found
                break
        
        if not messages:
            # Look for any element with OTP pattern
            all_elements = soup.find_all(['div', 'li', 'p', 'span'])
            for elem in all_elements:
                text = elem.get_text()
                if re.search(r'\b\d{4,6}\b', text) and len(text) < 300:
                    messages.append(elem)
        
        otps_found = []
        
        for msg in messages:
            text = msg.get_text()
            
            otp_match = re.search(r'\b\d{4,6}\b', text)
            if otp_match:
                otp_value = otp_match.group()
                
                phone_match = re.search(r'\+\d{10,15}', text)
                phone = phone_match.group() if phone_match else 'Unknown'
                
                service = 'Unknown'
                service_match = re.search(r'([A-Za-z0-9]+)\s*:', text)
                if service_match:
                    service = service_match.group(1)
                else:
                    common_services = ['Amazon', 'Google', 'Facebook', 'PayPal', 'Apple', 'WhatsApp', 'Instagram']
                    for s in common_services:
                        if s.lower() in text.lower():
                            service = s
                            break
                
                otps_found.append({
                    'otp': otp_value,
                    'text': text[:200],
                    'phone': phone,
                    'service': service,
                    'time': datetime.now().strftime('%H:%M:%S %d/%m')
                })
        
        return otps_found
        
    except Exception as e:
        print(f"Fetch error: {e}")
        LOGIN_STATUS = False
        SESSION_COOKIE = None
        return []

def auto_sync_numbers():
    """Background thread to sync numbers"""
    global numbers_list, LAST_NUMBERS_SYNC
    while True:
        time.sleep(1800)  # 30 minutes
        print("🔄 Auto-syncing numbers...")
        if LOGIN_STATUS:
            new_numbers = get_numbers_from_ivasms()
            if new_numbers:
                numbers_list = new_numbers
                LAST_NUMBERS_SYNC = datetime.now().strftime('%H:%M:%S')
                print(f"✅ Synced {len(numbers_list)} numbers")
        else:
            login_ivasms()

def auto_refresh_login():
    """Background thread to keep login alive"""
    while True:
        time.sleep(600)  # 10 minutes
        print("🔄 Auto-refreshing login...")
        login_ivasms()

# Start background threads
if IVASMS_EMAIL and IVASMS_PASSWORD:
    login_ivasms()
    
    refresh_thread = threading.Thread(target=auto_refresh_login, daemon=True)
    refresh_thread.start()
    
    sync_thread = threading.Thread(target=auto_sync_numbers, daemon=True)
    sync_thread.start()
    
    # Initial numbers sync
    numbers_list = get_numbers_from_ivasms()
    LAST_NUMBERS_SYNC = datetime.now().strftime('%H:%M:%S')

LAST_CHECK_TIME = None

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/otps')
def get_otps():
    return jsonify(otps[:50])

@app.route('/api/numbers', methods=['GET'])
def get_numbers():
    return jsonify(numbers_list)

@app.route('/api/sync-numbers', methods=['POST'])
def sync_numbers():
    global numbers_list, LAST_NUMBERS_SYNC
    new_numbers = get_numbers_from_ivasms()
    if new_numbers:
        numbers_list = new_numbers
        LAST_NUMBERS_SYNC = datetime.now().strftime('%H:%M:%S')
        return jsonify({
            'status': 'success',
            'total_numbers': len(numbers_list),
            'last_sync': LAST_NUMBERS_SYNC
        })
    return jsonify({
        'status': 'error',
        'message': 'Failed to sync numbers from iVASMS'
    })

@app.route('/api/check', methods=['POST'])
def check_otp():
    global otps, otp_cache, LAST_CHECK_TIME, LOGIN_STATUS
    
    if not IVASMS_EMAIL or not IVASMS_PASSWORD:
        return jsonify({
            'status': 'error',
            'message': 'iVASMS credentials not configured.'
        })
    
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
        'total_numbers': len(numbers_list),
        'ivasms_configured': bool(IVASMS_EMAIL and IVASMS_PASSWORD),
        'logged_in': LOGIN_STATUS,
        'last_check': LAST_CHECK_TIME,
        'last_login': LAST_LOGIN_TIME,
        'last_numbers_sync': LAST_NUMBERS_SYNC
    })

@app.route('/api/clear', methods=['POST'])
def clear():
    global otps, otp_cache
    otps = []
    otp_cache = set()
    return jsonify({'status': 'cleared'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
