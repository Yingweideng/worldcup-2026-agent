import os, requests
from country_map import COUNTRY

os.makedirs("flags", exist_ok=True)
BASE = "https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/72x72/"
# 如果 jsDelivr 不通,改用 unpkg:
# BASE = "https://unpkg.com/twemoji@latest/assets/72x72/"

def flag_to_filename(flag):
    return "-".join(f"{ord(c):x}" for c in flag if ord(c) != 0xFE0F) + ".png"

for en, info in COUNTRY.items():
    fname = flag_to_filename(info["flag"])
    url = BASE + fname
    path = f"flags/{fname}"
    if os.path.exists(path): continue
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and len(r.content) > 100:
            open(path, "wb").write(r.content)
            print(f"✓ {info['zh']} -> {fname}")
        else:
            print(f"✗ {info['zh']} HTTP {r.status_code}")
    except Exception as e:
        print(f"✗ {info['zh']} {e}")
