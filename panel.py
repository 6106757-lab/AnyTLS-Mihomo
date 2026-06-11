import os
import re
import base64
import urllib.parse
import subprocess
from flask import Flask, request, render_template_string, redirect, session, jsonify

app = Flask(__name__)
app.secret_key = 'anytls-panel-secret-key-v3'

CONFIG_DIR = '/root/.config/mihomo'
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.yaml')
CERT_PATH = os.path.join(CONFIG_DIR, 'server.crt')
KEY_PATH = os.path.join(CONFIG_DIR, 'server.key')

# 额外持久化存储路径
PWD_PATH = os.path.join(CONFIG_DIR, 'panel_pwd.txt')
IP_PATH = os.path.join(CONFIG_DIR, 'server_ip.txt')
DOMAIN_PATH = os.path.join(CONFIG_DIR, 'cert_domain.txt')
CERT_TYPE_PATH = os.path.join(CONFIG_DIR, 'cert_type.txt')
SNI_PATH = os.path.join(CONFIG_DIR, 'client_sni.txt')
FP_PATH = os.path.join(CONFIG_DIR, 'client_fp.txt')
INSECURE_PATH = os.path.join(CONFIG_DIR, 'client_insecure.txt')

mihomo_process = None

# --- 工具函数 ---
def get_file_content(path, default=""):
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return f.read().strip()
        except:
            pass
    return default

def write_file_content(path, content):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(content.strip() + '\n')
    except Exception as e:
        print(f"写入文件 {path} 出错:", e)

# 动态获取证书详情 (使用 openssl 解析)
def get_cert_details():
    details = {
        'subject': '未生成',
        'start_date': '未知',
        'end_date': '未知',
        'status': '未知'
    }
    if not os.path.exists(CERT_PATH):
        return details
    try:
        # 获取证书域名 (CN)
        subject_res = subprocess.run(
            ["openssl", "x509", "-subject", "-noout", "-in", CERT_PATH],
            capture_output=True, text=True, check=True
        )
        sub_str = subject_res.stdout.strip()
        cn_match = re.search(r'CN\s*=\s*([^,\n]+)', sub_str)
        if cn_match:
            details['subject'] = cn_match.group(1).strip()
        else:
            details['subject'] = sub_str

        # 获取生效与过期时间
        dates_res = subprocess.run(
            ["openssl", "x509", "-dates", "-noout", "-in", CERT_PATH],
            capture_output=True, text=True, check=True
        )
        dates_str = dates_res.stdout.strip()
        start_match = re.search(r'notBefore=(.*)', dates_str)
        end_match = re.search(r'notAfter=(.*)', dates_str)
        
        if start_match:
            details['start_date'] = start_match.group(1).strip()
        if end_match:
            details['end_date'] = end_match.group(1).strip()
            
        details['status'] = '生效中'
    except Exception as e:
        details['status'] = f"解析失败: {str(e)}"
    return details

# 自签名证书生成逻辑
def generate_self_signed(domain):
    if not domain:
        domain = "anytls"
    try:
        cmd = [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", 
            "-keyout", KEY_PATH, "-out", CERT_PATH, "-sha256", 
            "-days", "3650", "-nodes", "-subj", f"/CN={domain}"
        ]
        if "." in domain:
            cmd += ["-addext", f"subjectAltName=DNS:{domain}"]
        subprocess.run(cmd, check=True)
        return True
    except Exception as e:
        print("生成自签名证书出错:", e)
        return False

# 重启内核
def restart_mihomo_kernel():
    global mihomo_process
    if mihomo_process:
        try:
            mihomo_process.terminate()
            mihomo_process.wait(timeout=5)
        except Exception as e:
            print("停止旧进程出错:", e)
            
    print("正在启动新的 Mihomo 进程...")
    mihomo_process = subprocess.Popen(["/usr/local/bin/mihomo", "-d", CONFIG_DIR])

# 获取公网IP
def get_auto_ip():
    try:
        import urllib.request
        return urllib.request.urlopen('https://api.ipify.org', timeout=3).read().decode('utf-8')
    except:
        return "127.0.0.1"

# 获取面板密码
def get_panel_password():
    if os.path.exists(PWD_PATH):
        try:
            with open(PWD_PATH, 'r') as f:
                return f.read().strip()
        except:
            pass
    return "admin" # 默认密码

# 获取保存的公网IP
def get_server_ip():
    if os.path.exists(IP_PATH):
        try:
            with open(IP_PATH, 'r') as f:
                return f.read().strip()
        except:
            pass
    return get_auto_ip()

# 加载配置
def load_config_data():
    config = {
        'port': '8443',
        'users': [('username1', '密码1')],
        'padding_scheme': "stop=8\n0=30-30\n1=100-400\n2=400-500,c,500-1000,c,500-1000,c,500-1000,c,500-1000\n3=9-9,500-1000\n4=500-1000\n5=500-1000\n6=500-1000\n7=500-1000",
        'cert_type': get_file_content(CERT_TYPE_PATH, 'self_signed'),
        'cert_domain': get_file_content(DOMAIN_PATH, 'cloudflare.com'),
        'cert_pem': '',
        'key_pem': '',
        'server_ip': get_server_ip(),
        
        # 客户端导出参数
        'client_sni': get_file_content(SNI_PATH, 'cloudflare.com'),
        'client_fp': get_file_content(FP_PATH, 'chrome'),
        'client_insecure': get_file_content(INSECURE_PATH, 'true')
    }
    
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                content = f.read()
            
            port_match = re.search(r'port:\s*(\d+)', content)
            if port_match:
                config['port'] = port_match.group(1)
                
            users_block = re.search(r'users:\s*\n(.*?)\n\s*(?:certificate|private-key|padding-scheme):', content, re.DOTALL)
            if users_block:
                users_list = []
                for line in users_block.group(1).split('\n'):
                    line = line.strip()
                    if line and ':' in line:
                        u, p = line.split(':', 1)
                        users_list.append((u.strip(), p.strip()))
                if users_list:
                    config['users'] = users_list
                    
            padding_block = re.search(r'padding-scheme:\s*\|\s*\n(.*)', content, re.DOTALL)
            if padding_block:
                lines = padding_block.group(1).split('\n')
                clean_lines = []
                for l in lines:
                    if l.startswith('   '):
                        clean_lines.append(l[3:])
                    elif l.startswith('  '):
                        clean_lines.append(l[2:])
                    else:
                        clean_lines.append(l)
                config['padding_scheme'] = '\n'.join(clean_lines).strip()
        except Exception as e:
            print("解析配置出错:", e)

    if os.path.exists(CERT_PATH) and os.path.exists(KEY_PATH):
        try:
            with open(CERT_PATH, 'r') as f:
                config['cert_pem'] = f.read().strip()
            with open(KEY_PATH, 'r') as f:
                config['key_pem'] = f.read().strip()
        except:
            pass
            
    return config

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AnyTLS Mihomo 旗舰版面板</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
</head>
<body class="bg-gray-50 text-gray-800 min-h-screen">
    <div class="container mx-auto max-w-4xl py-8 px-4">
        <div class="bg-white rounded-xl shadow-lg overflow-hidden p-6 md:p-8">
            <!-- 头部 -->
            <div class="flex flex-col md:flex-row justify-between items-start md:items-center border-b pb-4 mb-6 gap-4">
                <div>
                    <h1 class="text-2xl font-bold text-indigo-600">AnyTLS-Mihomo (旗舰版面板)</h1>
                    <p class="text-xs text-gray-400 mt-1">完全掌控端口、账号、多维证书管理及客户端参数调校</p>
                </div>
                <div class="flex gap-2 w-full md:w-auto">
                    <button onclick="openTab('config-tab')" class="flex-1 md:flex-none text-sm bg-indigo-50 hover:bg-indigo-100 text-indigo-700 px-4 py-2 rounded font-semibold">系统配置</button>
                    <button onclick="openTab('security-tab')" class="flex-1 md:flex-none text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded font-semibold">安全设置</button>
                    <a href="/logout" class="text-center text-sm bg-red-100 hover:bg-red-200 text-red-700 px-4 py-2 rounded font-semibold">退出</a>
                </div>
            </div>

            <!-- TAB 1: 系统配置 -->
            <div id="config-tab" class="tab-content space-y-6">
                <!-- 动态订阅 -->
                <div class="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
                    <h3 class="text-sm font-bold text-indigo-800 mb-1">🔗 我的动态订阅链接</h3>
                    <p class="text-xs text-indigo-600 mb-2">可直接将此链接填入 NekoBox / v2rayN 等，一键同步此面板中配置的所有节点：</p>
                    <div class="flex gap-2">
                        <input type="text" id="subUrlInput" readonly class="flex-1 bg-white border border-indigo-300 rounded px-3 py-1.5 text-xs text-gray-600 outline-none">
                        <button onclick="copySubUrl()" class="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-4 rounded shadow">复制订阅</button>
                    </div>
                </div>

                <form id="configForm" class="space-y-6">
                    <!-- 基本网络配置 -->
                    <div class="bg-gray-50 p-4 rounded-lg border space-y-4">
                        <h3 class="text-sm font-bold text-gray-700 border-b pb-1">🌐 核心服务参数</h3>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs font-semibold text-gray-600 mb-1">服务器 IP 或 域名 (用于节点导出)</label>
                                <input type="text" name="server_ip" value="{{ config.server_ip }}" class="w-full border rounded px-3 py-1.5 text-sm outline-none" required>
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-gray-600 mb-1">服务端监听端口 (Port)</label>
                                <input type="number" name="port" id="portInput" value="{{ config.port }}" class="w-full border rounded px-3 py-1.5 text-sm outline-none" required min="1" max="65535">
                            </div>
                        </div>
                    </div>

                    <!-- 证书管理核心板块 -->
                    <div class="bg-gray-50 p-4 rounded-lg border space-y-4">
                        <div class="flex justify-between items-center border-b pb-1">
                            <h3 class="text-sm font-bold text-gray-700">🔒 证书配置与管理</h3>
                            <span class="text-xs text-gray-500">当前证书绑定域名: <strong class="text-indigo-600">{{ cert_details.subject }}</strong></span>
                        </div>

                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs font-semibold text-gray-600 mb-1">证书绑定域名/伪装域名 (Domain)</label>
                                <input type="text" name="cert_domain" id="certDomainInput" value="{{ config.cert_domain }}" placeholder="例如 cloudflare.com" class="w-full border rounded px-3 py-1.5 text-sm outline-none" required>
                                <span class="text-[10px] text-gray-400">用于自主签发及伪装</span>
                            </div>
                            <div class="bg-white border rounded p-3 text-xs space-y-1">
                                <span class="font-bold text-gray-700 block mb-1">📝 证书有效期：</span>
                                <div><span class="text-gray-500">生效时间：</span><span>{{ cert_details.start_date }}</span></div>
                                <div><span class="text-gray-500">过期时间：</span><span class="text-red-500 font-bold">{{ cert_details.end_date }}</span></div>
                            </div>
                        </div>

                        <!-- 证书类型选择 -->
                        <div class="pt-2">
                            <label class="block text-xs font-semibold text-gray-600 mb-2">证书来源类型</label>
                            <div class="flex gap-4">
                                <label class="flex items-center gap-1 cursor-pointer text-xs">
                                    <input type="radio" name="cert_type" value="self_signed" {% if config.cert_type == 'self_signed' %}checked{% endif %} onclick="toggleCertInput(false)"> 自动生成自签名证书 (基于上方域名)
                                </label>
                                <label class="flex items-center gap-1 cursor-pointer text-xs">
                                    <input type="radio" name="cert_type" value="custom" {% if config.cert_type == 'custom' %}checked{% endif %} onclick="toggleCertInput(true)"> 手动贴入真实域名证书 (CA签发)
                                </label>
                            </div>
                        </div>

                        <!-- 一键重签/续签按钮 -->
                        <div id="renewDiv" class="{% if config.cert_type == 'custom' %}hidden{% endif %}">
                            <button type="button" onclick="renewSelfSigned()" class="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-bold py-1.5 px-4 rounded border border-indigo-200">
                                🔄 基于新域名一键重签/续签 (10年期)
                            </button>
                        </div>

                        <!-- 自定义证书文本域 -->
                        <div id="customCertDiv" class="space-y-3 {% if config.cert_type == 'self_signed' %}hidden{% endif %}">
                            <div>
                                <span class="block text-xs text-gray-500 mb-1">公钥 PEM 内容 (server.crt)</span>
                                <textarea name="cert_pem" rows="4" placeholder="-----BEGIN CERTIFICATE-----" class="w-full border text-xs font-mono p-2 outline-none rounded">{{ config.cert_pem }}</textarea>
                            </div>
                            <div>
                                <span class="block text-xs text-gray-500 mb-1">私钥 PEM 内容 (server.key)</span>
                                <textarea name="key_pem" rows="4" placeholder="-----BEGIN PRIVATE KEY-----" class="w-full border text-xs font-mono p-2 outline-none rounded">{{ config.key_pem }}</textarea>
                            </div>
                        </div>
                    </div>

                    <!-- 客户端参数设置板 -->
                    <div class="bg-gray-50 p-4 rounded-lg border space-y-4">
                        <h3 class="text-sm font-bold text-gray-700 border-b pb-1">⚙️ 客户端导出参数调校</h3>
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div>
                                <label class="block text-xs font-semibold text-gray-600 mb-1">自定义 SNI (伪装目标)</label>
                                <input type="text" name="client_sni" id="clientSniInput" value="{{ config.client_sni }}" class="w-full border rounded px-3 py-1.5 text-sm outline-none" required>
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-gray-600 mb-1">TLS 指纹 (Fingerprint)</label>
                                <select name="client_fp" id="clientFpSelect" class="w-full border rounded px-3 py-1.5 text-sm outline-none bg-white">
                                    <option value="chrome" {% if config.client_fp == 'chrome' %}selected{% endif %}>chrome (推荐)</option>
                                    <option value="firefox" {% if config.client_fp == 'firefox' %}selected{% endif %}>firefox</option>
                                    <option value="safari" {% if config.client_fp == 'safari' %}selected{% endif %}>safari</option>
                                    <option value="edge" {% if config.client_fp == 'edge' %}selected{% endif %}>edge</option>
                                    <option value="randomized" {% if config.client_fp == 'randomized' %}selected{% endif %}>randomized</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-gray-600 mb-1">跳过证书验证 (AllowInsecure)</label>
                                <select name="client_insecure" id="clientInsecureSelect" class="w-full border rounded px-3 py-1.5 text-sm outline-none bg-white">
                                    <option value="true" {% if config.client_insecure == 'true' %}selected{% endif %}>true (自签名选此项)</option>
                                    <option value="false" {% if config.client_insecure == 'false' %}selected{% endif %}>false (真实域名证书选此项)</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <!-- 账号管理 -->
                    <div class="bg-gray-50 p-4 rounded-lg border space-y-4">
                        <h3 class="text-sm font-bold text-gray-700 border-b pb-1">👥 用户管理与一键分享</h3>
                        <div id="usersContainer" class="space-y-2">
                            {% for user, pwd in config.users %}
                            <div class="flex gap-2 user-row items-center">
                                <input type="text" name="username[]" value="{{ user }}" placeholder="用户名" class="flex-1 border rounded px-3 py-1.5 text-sm outline-none" required>
                                <input type="text" name="password[]" value="{{ pwd }}" placeholder="密码" class="flex-1 border rounded px-3 py-1.5 text-sm outline-none" required>
                                <button type="button" onclick="showShare('{{ user }}', '{{ pwd }}')" class="bg-green-500 hover:bg-green-600 text-white px-4 py-1.5 rounded text-xs font-bold shadow">生成连接</button>
                                <button type="button" onclick="removeUserRow(this)" class="bg-red-500 hover:bg-red-600 text-white px-4 py-1.5 rounded text-xs">删除</button>
                            </div>
                            {% endfor %}
                        </div>
                        <button type="button" onclick="addUserRow()" class="text-xs bg-indigo-50 hover:bg-indigo-100 text-indigo-600 font-semibold px-4 py-2 rounded border border-indigo-100">
                            + 添加新用户
                        </button>
                    </div>

                    <!-- Padding-Scheme -->
                    <div class="bg-gray-50 p-4 rounded-lg border space-y-2">
                        <h3 class="text-sm font-bold text-gray-700 border-b pb-1">📉 自定义混淆策略 (Padding-Scheme)</h3>
                        <textarea name="padding_scheme" rows="6" class="w-full border rounded p-2 font-mono text-sm outline-none bg-white" required>{{ config.padding_scheme }}</textarea>
                    </div>

                    <div class="pt-4 border-t flex items-center justify-between">
                        <button type="submit" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold px-8 py-3 rounded shadow">
                            保存并重启生效
                        </button>
                        <span id="statusMsg" class="text-sm font-semibold"></span>
                    </div>
                </form>
            </div>

            <!-- TAB 2: 安全设置 -->
            <div id="security-tab" class="tab-content hidden space-y-6">
                <div class="bg-gray-50 rounded-lg p-6 border">
                    <h3 class="text-lg font-bold text-gray-800 mb-4">🔑 修改面板登录密码</h3>
                    <form id="pwdForm" class="space-y-4">
                        <div>
                            <label class="block text-sm text-gray-600 mb-1">输入新密码</label>
                            <input type="password" name="new_password" class="w-full md:w-1/2 border rounded px-3 py-2 outline-none" required minlength="4">
                        </div>
                        <button type="submit" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold px-6 py-2 rounded">确认保存</button>
                        <span id="pwdStatus" class="text-sm font-semibold block mt-2"></span>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <!-- 二维码分享弹窗 -->
    <div id="shareModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center hidden p-4 z-50">
        <div class="bg-white rounded-xl shadow-lg max-w-md w-full p-6 space-y-4">
            <div class="flex justify-between items-center border-b pb-2">
                <h3 class="font-bold text-gray-800 text-lg">节点一键导入</h3>
                <button onclick="closeShare()" class="text-gray-400 hover:text-gray-600 text-xl font-bold">&times;</button>
            </div>
            <div>
                <p class="text-xs text-gray-500 mb-1">一键导入链接：</p>
                <div class="flex gap-1">
                    <input type="text" id="shareUrlInput" readonly class="flex-1 border bg-gray-50 rounded px-2 py-1 text-xs outline-none">
                    <button onclick="copyShareUrl()" class="bg-indigo-600 text-white text-xs px-3 py-1 rounded">复制</button>
                </div>
            </div>
            <div class="flex flex-col items-center justify-center p-4 bg-gray-50 rounded">
                <span class="text-xs text-gray-500 mb-2">使用客户端扫码直连：</span>
                <div id="qrcode" class="border p-2 bg-white rounded"></div>
            </div>
        </div>
    </div>

    <script>
        function openTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            document.getElementById(tabId).classList.remove('hidden');
        }

        function addUserRow() {
            const container = document.getElementById('usersContainer');
            const row = document.createElement('div');
            row.className = 'flex gap-2 user-row items-center';
            row.innerHTML = `
                <input type="text" name="username[]" placeholder="用户名" class="flex-1 border rounded px-3 py-1.5 text-sm outline-none" required>
                <input type="text" name="password[]" placeholder="密码" class="flex-1 border rounded px-3 py-1.5 text-sm outline-none" required>
                <button type="button" class="bg-gray-300 text-gray-500 px-4 py-1.5 rounded text-xs font-bold cursor-not-allowed" disabled>保存后可用</button>
                <button type="button" onclick="removeUserRow(this)" class="bg-red-500 hover:bg-red-600 text-white px-4 py-1.5 rounded text-xs">删除</button>
            `;
            container.appendChild(row);
        }

        function removeUserRow(btn) {
            const rows = document.querySelectorAll('.user-row');
            if (rows.length > 1) {
                btn.parentElement.remove();
            } else {
                alert("至少需要保留一个账号！");
            }
        }

        function toggleCertInput(show) {
            const div = document.getElementById('customCertDiv');
            const renewDiv = document.getElementById('renewDiv');
            if (show) {
                div.classList.remove('hidden');
                renewDiv.classList.add('hidden');
            } else {
                div.classList.add('hidden');
                renewDiv.classList.remove('hidden');
            }
        }

        // 一键重签/续签证书
        function renewSelfSigned() {
            const domain = document.getElementById('certDomainInput').value;
            if(!domain) {
                alert("请先在域名输入框中填写你要绑定的域名！");
                return;
            }
            if(!confirm("确认要为域名 [" + domain + "] 重新签发一张 10 年期的自签名证书吗？")) return;
            
            fetch('/renew_cert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: "domain=" + encodeURIComponent(domain)
            })
            .then(res => res.json())
            .then(data => {
                if(data.status === 'success') {
                    alert("证书重签成功！重启生效。");
                    location.reload();
                } else {
                    alert("重签失败: " + data.message);
                }
            });
        }

        // 提交配置
        document.getElementById('configForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const status = document.getElementById('statusMsg');
            status.className = "text-sm font-semibold text-blue-600";
            status.innerText = "正在保存并重新构建内核中...";

            const formData = new FormData(this);
            fetch('/save', { method: 'POST', body: formData })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    status.className = "text-sm font-semibold text-green-600";
                    status.innerText = "🎉 配置成功应用，内核已热重启！";
                    setTimeout(() => { location.reload(); }, 1500);
                } else {
                    status.className = "text-sm font-semibold text-red-600";
                    status.innerText = "❌ 失败: " + data.message;
                }
            });
        });

        // 修改密码
        document.getElementById('pwdForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const status = document.getElementById('pwdStatus');
            status.innerText = "正在保存密码...";
            status.className = "text-sm text-blue-500";

            const formData = new FormData(this);
            fetch('/change_password', { method: 'POST', body: formData })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    status.className = "text-sm text-green-600";
                    status.innerText = "🎉 密码更新成功！";
                    this.reset();
                } else {
                    status.className = "text-sm text-red-600";
                    status.innerText = "❌ 失败: " + data.message;
                }
            });
        });

        // 订阅配置
        const host = window.location.hostname;
        const panelPort = window.location.port ? ":" + window.location.port : "";
        document.getElementById('subUrlInput').value = "http://" + host + panelPort + "/sub";

        function copySubUrl() {
            const input = document.getElementById('subUrlInput');
            input.select();
            document.execCommand('copy');
            alert('订阅已复制，请填入客户端。');
        }

        // 分享逻辑
        let qrcodeInstance = null;
        function showShare(user, pwd) {
            const serverIp = window.location.hostname;
            const port = document.getElementById('portInput').value;
            const sni = document.getElementById('clientSniInput').value;
            const fp = document.getElementById('clientFpSelect').value;
            const insecure = document.getElementById('clientInsecureSelect').value;
            
            const encodedPwd = encodeURIComponent(pwd);
            const remarks = encodeURIComponent("AnyTLS-" + user);
            
            // 构造完美的 anytls 客户端链接
            const shareUrl = "anytls://" + encodedPwd + "@" + serverIp + ":" + port + 
                             "?allowInsecure=" + insecure + "&sni=" + encodeURIComponent(sni) + 
                             "&fingerprint=" + encodeURIComponent(fp) + "#" + remarks;

            document.getElementById('shareUrlInput').value = shareUrl;
            document.getElementById('shareModal').classList.remove('hidden');

            const qrContainer = document.getElementById('qrcode');
            qrContainer.innerHTML = "";
            qrcodeInstance = new QRCode(qrContainer, {
                text: shareUrl,
                width: 180,
                height: 180,
                colorDark: "#000000",
                colorLight: "#ffffff",
                correctLevel: QRCode.CorrectLevel.L
            });
        }

        function closeShare() {
            document.getElementById('shareModal').classList.add('hidden');
        }

        function copyShareUrl() {
            const input = document.getElementById('shareUrlInput');
            input.select();
            document.execCommand('copy');
            alert('一键导入节点已复制！');
        }
    </script>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>登录 AnyTLS 配置面板</title>
    <meta charset="utf-8">
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen">
    <div class="bg-white p-8 rounded-lg shadow-md w-full max-w-sm">
        <h2 class="text-xl font-bold mb-4 text-center text-indigo-600">AnyTLS-Mihomo 面板</h2>
        {% if error %}<div class="bg-red-100 text-red-700 p-2 rounded mb-4 text-sm">{{ error }}</div>{% endif %}
        <form action="/login" method="POST" class="space-y-4">
            <div>
                <label class="block text-sm text-gray-600">请输入登录密码</label>
                <input type="password" name="password" class="w-full border rounded px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-400" required autofocus>
            </div>
            <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 rounded">进入面板</button>
        </form>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    if not session.get('logged_in'):
        return render_template_string(LOGIN_TEMPLATE)
    config = load_config_data()
    cert_details = get_cert_details()
    return render_template_string(HTML_TEMPLATE, config=config, cert_details=cert_details)

@app.route('/login', methods=['POST'])
def login():
    pwd = request.form.get('password')
    if pwd == get_panel_password():
        session['logged_in'] = True
        return redirect('/')
    return render_template_string(LOGIN_TEMPLATE, error="密码错误！")

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect('/')

# 节点订阅接口
@app.route('/sub')
def sub_route():
    config = load_config_data()
    server_ip = get_server_ip()
    port = config['port']
    sni = config['client_sni']
    fp = config['client_fp']
    insecure = config['client_insecure']
    
    links = []
    for u, p in config['users']:
        encoded_pwd = urllib.parse.quote(p)
        remarks = urllib.parse.quote(f"AnyTLS-{u}")
        link = f"anytls://{encoded_pwd}@{server_ip}:{port}?allowInsecure={insecure}&sni={urllib.parse.quote(sni)}&fingerprint={urllib.parse.quote(fp)}#{remarks}"
        links.append(link)
        
    sub_str = "\n".join(links)
    b64_sub = base64.b64encode(sub_str.encode('utf-8')).decode('utf-8')
    return b64_sub, 200, {'Content-Type': 'text/plain; charset=utf-8'}

# 一键续签 / 自签证书接口
@app.route('/renew_cert', methods=['POST'])
def renew_cert():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': '未登录'})
    domain = request.form.get('domain', 'cloudflare.com')
    
    # 写入域名
    write_file_content(DOMAIN_PATH, domain)
    # 强制自签名
    write_file_content(CERT_TYPE_PATH, 'self_signed')
    
    success = generate_self_signed(domain)
    if success:
        # 重启内核以加载新证书
        restart_mihomo_kernel()
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': '证书生成失败，请检查 openssl 是否支持'})

@app.route('/change_password', methods=['POST'])
def change_password():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': '未登录'})
    new_pwd = request.form.get('new_password')
    if not new_pwd:
        return jsonify({'status': 'error', 'message': '密码不能为空'})
    
    write_file_content(PWD_PATH, new_pwd)
    return jsonify({'status': 'success'})

@app.route('/save', methods=['POST'])
def save_config():
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': '未登录'})
        
    try:
        port = request.form.get('port')
        server_ip = request.form.get('server_ip')
        cert_domain = request.form.get('cert_domain')
        cert_type = request.form.get('cert_type')
        cert_pem = request.form.get('cert_pem')
        key_pem = request.form.get('key_pem')
        padding_scheme = request.form.get('padding_scheme')
        
        # 客户端参数
        client_sni = request.form.get('client_sni')
        client_fp = request.form.get('client_fp')
        client_insecure = request.form.get('client_insecure')
        
        usernames = request.form.getlist('username[]')
        passwords = request.form.getlist('password[]')
        
        # 保存辅助信息
        write_file_content(IP_PATH, server_ip)
        write_file_content(DOMAIN_PATH, cert_domain)
        write_file_content(CERT_TYPE_PATH, cert_type)
        write_file_content(SNI_PATH, client_sni)
        write_file_content(FP_PATH, client_fp)
        write_file_content(INSECURE_PATH, client_insecure)
        
        # 处理证书
        if cert_type == 'self_signed':
            # 基于输入的域名，生成 10 年期的证书
            generate_self_signed(cert_domain)
        else:
            with open(CERT_PATH, 'w') as f:
                f.write(cert_pem.strip() + '\n')
            with open(KEY_PATH, 'w') as f:
                f.write(key_pem.strip() + '\n')
                
        # 重新格式化并写入 YAML
        users_str_list = []
        for u, p in zip(usernames, passwords):
            if u.strip() and p.strip():
                users_str_list.append(f"    {u.strip()}: {p.strip()}")
        users_str = '\n'.join(users_str_list)
        
        padding_lines = [f"   {line}" for line in padding_scheme.strip().split('\n')]
        padding_str = '\n'.join(padding_lines)
        
        yaml_content = f"""listeners:
- name: anytls-in-1
  type: anytls
  port: {port}
  listen: 0.0.0.0
  users:
{users_str}
  certificate: {CERT_PATH}
  private-key: {KEY_PATH}
  padding-scheme: |
{padding_str}
"""
        with open(CONFIG_PATH, 'w') as f:
            f.write(yaml_content)
            
        # 重启进程
        restart_mihomo_kernel()
        return jsonify({'status': 'success'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    restart_mihomo_kernel()
    app.run(host='0.0.0.0', port=8888)
