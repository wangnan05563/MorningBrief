
import os
# Fix tunnel_providers.py
p1 = r'D:/code/otherProjects/20_News/backend/app/services/tunnel_providers.py'
with open(p1, 'r', encoding='utf-8') as f:
    c = f.read()
old = '            if not isinstance(handlers, dict) or self._path_prefix not in handlers:\n                return None\n            return f"https://{host}{self._path_prefix}"'
new = '            if not isinstance(handlers, dict) or self._path_prefix not in handlers:\n                # fallback: Funnel已启用，直接构造URL\n                logger.info("[tailscale] Handlers check failed", self._path_prefix)\n                return f"https://{host}{self._path_prefix}"\n            return f"https://{host}{self._path_prefix}"'
if old in c:
    c = c.replace(old, new)
    with open(p1, 'w', encoding='utf-8') as f:
        f.write(c)
    print('1. Fixed tunnel_providers.py')
else:
    print('1. NOT FOUND')
    print(c[c.find('if not isinstance(handlers'):c.find('if not isinstance(handlers')+300])
