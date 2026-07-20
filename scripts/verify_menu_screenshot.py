"""通过 Chrome DevTools Protocol 注入登录态并截取后台菜单截图。

用于菜单分组改造的视觉验证：headless 模式下无法触发 Element Plus 登录按钮，
所以先调用后端 /admin/api/v1/auth/login 拿到 token，再通过 CDP 注入
localStorage，导航到 /review 后截图。

用法：python verify_menu_screenshot.py <token>
"""
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse

CHROME_PORT = 9222
TEMP_PROFILE = os.path.join(os.environ.get('TEMP', '/tmp'), 'chrome_menu_verify')


def find_chrome():
    candidates = [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    raise RuntimeError('Chrome/Edge not found')


def start_chrome():
    if os.path.exists(TEMP_PROFILE):
        shutil.rmtree(TEMP_PROFILE, ignore_errors=True)
    os.makedirs(TEMP_PROFILE, exist_ok=True)
    chrome = find_chrome()
    proc = subprocess.Popen(
        [
            chrome,
            '--headless=new',
            '--disable-gpu',
            '--remote-debugging-port=%d' % CHROME_PORT,
            '--user-data-dir=%s' % TEMP_PROFILE,
            '--no-first-run',
            '--no-default-browser-check',
            '--hide-scrollbars',
            '--window-size=1440,900',
            'about:blank',
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # 等待 debugging 端口就绪
    for _ in range(30):
        try:
            with socket.create_connection(('127.0.0.1', CHROME_PORT), timeout=1):
                return proc
        except OSError:
            time.sleep(0.3)
    raise RuntimeError('Chrome debugging port not ready')


def get_ws_url():
    resp = urllib.request.urlopen(
        'http://127.0.0.1:%d/json/list' % CHROME_PORT, timeout=5
    )
    tabs = json.loads(resp.read().decode('utf-8'))
    # 选 about:blank 那个
    for t in tabs:
        if t.get('type') == 'page':
            return t['webSocketDebuggerUrl']
    raise RuntimeError('No page tab found')


class WS:
    def __init__(self, url):
        p = urlparse(url)
        self.host = p.hostname
        self.port = p.port
        self.path = p.path + (('?' + p.query) if p.query else '')
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self._handshake()

    def _handshake(self):
        key = base64.b64encode(os.urandom(16)).decode('ascii')
        req = (
            'GET %s HTTP/1.1\r\n'
            'Host: %s:%d\r\n'
            'Upgrade: websocket\r\n'
            'Connection: Upgrade\r\n'
            'Sec-WebSocket-Key: %s\r\n'
            'Sec-WebSocket-Version: 13\r\n'
            '\r\n'
        ) % (self.path, self.host, self.port, key)
        self.sock.sendall(req.encode('ascii'))
        resp = b''
        while b'\r\n\r\n' not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError('WS handshake closed')
            resp += chunk
        if b'101' not in resp.split(b'\r\n')[0]:
            raise RuntimeError('WS handshake failed: %s' % resp[:200])

    def send(self, payload):
        data = payload.encode('utf-8')
        header = bytearray([0x81])  # FIN + text
        mask = os.urandom(4)
        n = len(data)
        if n <= 125:
            header.append(0x80 | n)
        elif n <= 65535:
            header.append(0x80 | 126)
            header.extend(struct.pack('>H', n))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack('>Q', n))
        header.extend(mask)
        masked = bytearray(data)
        for i in range(len(masked)):
            masked[i] ^= mask[i % 4]
        self.sock.sendall(bytes(header) + bytes(masked))

    def recv(self):
        first = self._recv_n(1)[0]
        second = self._recv_n(1)[0]
        masked = (second & 0x80) != 0
        length = second & 0x7F
        if length == 126:
            length = struct.unpack('>H', self._recv_n(2))[0]
        elif length == 127:
            length = struct.unpack('>Q', self._recv_n(8))[0]
        mask = self._recv_n(4) if masked else None
        payload = self._recv_n(length)
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return payload.decode('utf-8')

    def _recv_n(self, n):
        buf = b''
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise RuntimeError('socket closed')
            buf += chunk
        return buf

    def call(self, msg_id, method, params=None):
        cmd = {'id': msg_id, 'method': method}
        if params:
            cmd['params'] = params
        self.send(json.dumps(cmd))
        # 循环接收，跳过事件通知，直到拿到对应 id 的响应
        while True:
            data = json.loads(self.recv())
            if data.get('id') == msg_id:
                return data

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def main():
    if len(sys.argv) < 2:
        print('Usage: python verify_menu_screenshot.py <token>')
        sys.exit(1)
    token = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else 'menu_screenshot.png'

    proc = start_chrome()
    try:
        ws_url = get_ws_url()
        print('WS URL:', ws_url)
        ws = WS(ws_url)

        # 先导航到目标 origin，才能设置该 origin 的 localStorage
        ws.call(1, 'Page.enable')
        nav = ws.call(2, 'Page.navigate', {'url': 'http://127.0.0.1:8000/login'})
        print('Navigate to /login:', nav.get('result', {}).get('frameId', ''))
        time.sleep(2)

        # 注入 localStorage（路由守卫读 admin_token/admin_role）
        js = (
            'localStorage.setItem("admin_token", "%s"); '
            'localStorage.setItem("admin_username", "admin"); '
            'localStorage.setItem("admin_role", "admin"); '
            '"ok"'
        ) % token
        r = ws.call(3, 'Runtime.evaluate', {'expression': js})
        print('Inject localStorage:', r.get('result', {}).get('result', {}).get('value'))

        # 导航到 /review（admin 默认页），等待菜单渲染
        ws.call(4, 'Page.navigate', {'url': 'http://127.0.0.1:8000/review'})
        time.sleep(3)

        # 收集 console 错误
        errors = ws.call(5, 'Runtime.evaluate', {
            'expression': '(function(){return (window.__errors||[]).join("\\n")})()'
        })

        # 截图
        shot = ws.call(6, 'Page.captureScreenshot', {'format': 'png'})
        data = shot.get('result', {}).get('data')
        if data:
            img = base64.b64decode(data)
            out_path = os.path.abspath(output)
            with open(out_path, 'wb') as f:
                f.write(img)
            print('Screenshot saved:', out_path, '(%d bytes)' % len(img))
        else:
            print('Screenshot failed:', shot)

        ws.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == '__main__':
    main()
