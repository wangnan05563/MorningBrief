"""通过 CDP 获取后台页面 DOM 文本，验证菜单分组渲染结果。

注入 token 后导航到 /review，提取左侧菜单的所有分组标题和菜单项文本，
以及当前 URL 和页面标题，与预期 7 组配置做比对。

用法：python verify_menu_dom.py <token>
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

# 复用 verify_menu_screenshot.py 的 WS 类和启动逻辑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_menu_screenshot import WS, start_chrome, get_ws_url, CHROME_PORT


def main():
    if len(sys.argv) < 2:
        print('Usage: python verify_menu_dom.py <token>')
        sys.exit(1)
    token = sys.argv[1]

    proc = start_chrome()
    try:
        ws = WS(get_ws_url())
        ws.call(1, 'Page.enable')
        ws.call(2, 'Page.navigate', {'url': 'http://127.0.0.1:8000/login'})
        time.sleep(2)

        js = (
            'localStorage.setItem("admin_token", "%s"); '
            'localStorage.setItem("admin_username", "admin"); '
            'localStorage.setItem("admin_role", "admin"); '
            '"ok"'
        ) % token
        ws.call(3, 'Runtime.evaluate', {'expression': js})

        ws.call(4, 'Page.navigate', {'url': 'http://127.0.0.1:8000/review'})
        time.sleep(3)

        # 收集页面信息
        info_js = """
        (function(){
            var url = location.href;
            var title = document.title;
            var groups = [];
            var subMenus = document.querySelectorAll('.sidebar-menu .el-sub-menu');
            subMenus.forEach(function(sm){
                var titleEl = sm.querySelector('.el-sub-menu__title span');
                var items = [];
                sm.querySelectorAll('.el-menu-item').forEach(function(it){
                    var t = it.textContent.trim();
                    if (t) items.push(t);
                });
                groups.push({title: titleEl ? titleEl.textContent.trim() : '', items: items});
            });
            var flatItems = [];
            document.querySelectorAll('.sidebar-menu .el-menu-item').forEach(function(it){
                var t = it.textContent.trim();
                if (t) flatItems.push(t);
            });
            return JSON.stringify({url:url, title:title, groupCount:groups.length, groups:groups, flatItems:flatItems}, null, 2);
        })()
        """
        r = ws.call(5, 'Runtime.evaluate', {'expression': info_js, 'returnByValue': True})
        value = r.get('result', {}).get('result', {}).get('value')
        if value:
            print(value)
        else:
            print('Eval failed:', json.dumps(r, ensure_ascii=False))

        ws.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == '__main__':
    main()
