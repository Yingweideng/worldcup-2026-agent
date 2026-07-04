import os, json, re, requests
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
from pilmoji.source import BaseSource, MicrosoftEmojiSource
from country_map import COUNTRY

# ── 画布与配色 ────────────────────────────────────────────
W, H        = 1400, 1500
BG          = "#0a1f4d"
CARD        = "#1a3a7a"
CARD_DONE   = "#1f4a8c"
GOLD        = "#d4a017"
WHITE       = "#ffffff"
GRAY        = "#888888"

# ── 布局参数(七列互不重叠) ────────────────────────────
COL_W   = 150
CARD_H  = 60
TOP     = 140
BOTTOM  = H - 100

X_R16L = 20
X_R8L  = 200
X_QFL  = 380
CTR_CARD_X = 610            # 中央走廊
X_QFR  = 820
X_R8R  = 1020
X_R16R = 1200

MID_X  = CTR_CARD_X + COL_W // 2   # 中央纵向轴

# 中央纵向坐标
sf_top_y = 380
sf_bot_y = 940
fin_y    = 680
third_y  = 1180

# ── API ────────────────────────────────────────────────────
API = "https://api.football-data.org/v4/competitions/WC/matches"
HEADERS = {"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN",
                                     "17589beb74fb4aebabc7e64b43f7f651")}

def fetch():
    r = requests.get(API, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()["matches"]

# ── Bracket 路径 ───────────────────────────────────────────
R16_ORDER = [
    ("Germany","Paraguay"), ("France","Sweden"),
    ("South Africa","Canada"), ("Netherlands","Morocco"),
    ("Colombia","Croatia"), ("Spain","Austria"),
    ("United States","Bosnia-Herzegovina"), ("Belgium","Korea Republic"),
    ("Brazil","Japan"), ("Ivory Coast","Norway"),
    ("Mexico","Ecuador"), ("England","Senegal"),
    ("Argentina","Cape Verde"), ("Australia","Egypt"),
    ("Switzerland","Iran"), ("Portugal","Ghana"),
]
NEXT = {i: (i // 2, "home" if i % 2 == 0 else "away") for i in range(16)}

STAGE_MAP = {
    "LAST_32": "R16",
    "LAST_16": "R8",
    "QUARTER_FINALS": "QF",
    "SEMI_FINALS": "SF",
    "THIRD_PLACE": "3RD",
    "THIRD_PLACE_FINAL": "3RD",
    "FINAL": "FINAL",
}

# ── 统一的 dict match 结构 ─────────────────────────────────
def _empty_match():
    return {"homeTeam": {"name": ""}, "awayTeam": {"name": ""},
            "status": "SCHEDULED",
            "score": {"fullTime": {"home": None, "away": None},
                      "winner": None,
                      "penalties": {"home": None, "away": None}}}

def _winner_name(m):
    w = m.get("score", {}).get("winner")
    if w == "HOME_TEAM": return m["homeTeam"]["name"]
    if w == "AWAY_TEAM": return m["awayTeam"]["name"]
    return None

# ── 解析 + 推进 ────────────────────────────────────────────
def build_bracket(matches):
    bracket = {
        "R16":  [_empty_match() for _ in range(16)],
        "R8":   [_empty_match() for _ in range(8)],
        "QF":   [_empty_match() for _ in range(4)],
        "SF":   [_empty_match() for _ in range(2)],
        "3RD":  _empty_match(),
        "FINAL":_empty_match(),
    }
    for i, (h, a) in enumerate(R16_ORDER):
        bracket["R16"][i]["homeTeam"]["name"] = h
        bracket["R16"][i]["awayTeam"]["name"] = a

    for m in matches:
        stage = STAGE_MAP.get(m.get("stage", ""))
        if not stage: continue
        h = m.get("homeTeam", {}).get("name", "")
        a = m.get("awayTeam", {}).get("name", "")

        if stage == "R16":
            key = (h, a) if (h, a) in R16_ORDER else (a, h)
            if key not in R16_ORDER: continue
            idx = R16_ORDER.index(key)
            bracket["R16"][idx] = m
            # 胜者自动晋级(只填空 slot)
            if m.get("status") == "FINISHED":
                w = _winner_name(m)
                if w:
                    ni, side = NEXT[idx]
                    if not bracket["R8"][ni][f"{side}Team"]["name"]:
                        bracket["R8"][ni][f"{side}Team"]["name"] = w
        else:
            pool = bracket[stage] if isinstance(bracket[stage], list) else [bracket[stage]]
            slot = next((x for x in pool
                         if {x["homeTeam"]["name"], x["awayTeam"]["name"]} == {h, a}), None)
            if slot is None:
                slot = next((x for x in pool
                             if not x["homeTeam"]["name"] or not x["awayTeam"]["name"]), None)
            if slot is None: continue
            slot.update(m)

    return bracket

# ── 文本输出 ───────────────────────────────────────────────
def fmt_match(m):
    h_en = m.get("homeTeam", {}).get("name", "")
    a_en = m.get("awayTeam", {}).get("name", "")
    if not h_en and not a_en: return "待定  VS  待定\n"
    h = COUNTRY.get(h_en, {"zh": h_en or "待定", "flag": ""})
    a = COUNTRY.get(a_en, {"zh": a_en or "待定", "flag": ""})
    if m.get("status") == "FINISHED":
        s = m["score"]["fullTime"]
        return f"{h['flag']} {h['zh']} {s['home']} : {s['away']} {a['flag']} {a['zh']}\n"
    return f"{h['flag']} {h['zh']}  VS  {a['flag']} {a['zh']}\n"

def export_text(bracket):
    out = ["======== 2026 美加墨世界杯 ========\n",
           f"更新时间: {datetime.now():%Y-%m-%d %H:%M}\n",
           "【1/16 决赛(32 强)】\n"]
    out += [fmt_match(m) for m in bracket["R16"]]
    out += ["【1/8 决赛】\n"]  + [fmt_match(m) for m in bracket["R8"]]
    out += ["【1/4 决赛】\n"]  + [fmt_match(m) for m in bracket["QF"]]
    out += ["【半决赛】\n"]    + [fmt_match(m) for m in bracket["SF"]]
    out += ["【季军赛】\n",     fmt_match(bracket["3RD"])]
    out += ["【决赛】\n",       fmt_match(bracket["FINAL"])]
    return "".join(out)

# ── emoji 本地源 ───────────────────────────────────────────
class LocalFlagSource(BaseSource):
    def get_emoji(self, emoji: str):
        codepoints = "-".join(f"{ord(c):x}" for c in emoji if ord(c) != 0xFE0F)
        path = f"flags/{codepoints}.png"
        if os.path.exists(path):
            return BytesIO(open(path, "rb").read())
        return None
    def get_discord_emoji(self, id: int): return None

def _emoji_source():
    return LocalFlagSource if os.path.isdir("flags") else MicrosoftEmojiSource

# ── 字体 ───────────────────────────────────────────────────
def F(bold, size):
    path = r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"
    return ImageFont.truetype(path, size)

# ── 渲染 ───────────────────────────────────────────────────
def render_png(bracket, out_path):
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    src  = _emoji_source()

    f_title = F(True, 48)
    f_sub   = F(False, 20)
    f_label = F(True, 16)
    f_body  = F(False, 16)
    f_score = F(True, 18)
    f_small = F(False, 14)
    f_champ = F(True, 22)

    draw.text((W // 2, 50), "2026 美加墨世界杯", fill=GOLD,  font=f_title, anchor="mm")
    draw.text((W // 2, 90), "淘汰赛对阵图 · 32强", fill=WHITE, font=f_sub,   anchor="mm")

    def card_y(idx, total):
        step = (BOTTOM - TOP) / total
        return TOP + idx * step + (step - CARD_H) / 2

    def safe_emoji_text(xy, text, font, fill):
        try:
            with Pilmoji(img, source=src) as p:
                p.text(xy, text, font=font, fill=fill)
        except Exception:
            clean = re.sub(r'[\U0001F1E6-\U0001F1FF]', '', text).strip()
            draw.text(xy, clean, font=font, fill=fill)

    def card(x, y, m, w=COL_W):
        finished = m.get("status") == "FINISHED"
        color = CARD_DONE if finished else CARD
        try:
            draw.rounded_rectangle([x, y, x + w, y + CARD_H], 6, fill=color, outline=GOLD)
        except TypeError:
            draw.rectangle([x, y, x + w, y + CARD_H], fill=color, outline=GOLD)

        h_en = m.get("homeTeam", {}).get("name", "")
        a_en = m.get("awayTeam", {}).get("name", "")
        h = COUNTRY.get(h_en, {"zh": h_en or "待定", "flag": ""})
        a = COUNTRY.get(a_en, {"zh": a_en or "待定", "flag": ""})

        safe_emoji_text((x + 8, y + 6),
                        f"{h['flag']} {h['zh']}" if h_en else "待定",
                        f_body, WHITE)
        safe_emoji_text((x + 8, y + CARD_H - 22),
                        f"{a['flag']} {a['zh']}" if a_en else "待定",
                        f_body, WHITE)

        if finished:
            s = m["score"]["fullTime"]
            draw.text((x + w - 8, y + 6),           str(s["home"]), fill=GOLD, font=f_score, anchor="ra")
            draw.text((x + w - 8, y + CARD_H - 22), str(s["away"]), fill=GOLD, font=f_score, anchor="ra")
        else:
            draw.text((x + w - 8, y + CARD_H // 2 - 8), "VS",
                      fill=GOLD, font=f_score, anchor="ra")

    def connect(x1, y1, x2, y2):
        mx = (x1 + x2) // 2
        draw.line([(x1, y1), (mx, y1), (mx, y2), (x2, y2)], fill=GOLD, width=2)

    def label(x, y, t):
        draw.text((x, y), t, fill=GOLD, font=f_label, anchor="mm")

    # 顶部列标签
    label(X_R16L + COL_W // 2, TOP - 35, "1/16 决赛")
    label(X_R8L  + COL_W // 2, TOP - 35, "1/8 决赛")
    label(X_QFL  + COL_W // 2, TOP - 35, "1/4 决赛")
    label(X_QFR  + COL_W // 2, TOP - 35, "1/4 决赛")
    label(X_R8R  + COL_W // 2, TOP - 35, "1/8 决赛")
    label(X_R16R + COL_W // 2, TOP - 35, "1/16 决赛")

    # 左侧 R16
    ys_r16l = []
    for i in range(8):
        y = card_y(i, 8); card(X_R16L, y, bracket["R16"][i])
        ys_r16l.append(y + CARD_H // 2)

    # 左侧 R8(出 R16 右边缘 → 进 R8 左边缘)
    ys_r8l = []
    for i in range(4):
        y = card_y(i, 4); card(X_R8L, y, bracket["R8"][i])
        cy = y + CARD_H // 2; ys_r8l.append(cy)
        connect(X_R16L + COL_W, ys_r16l[i * 2],     X_R8L, cy)
        connect(X_R16L + COL_W, ys_r16l[i * 2 + 1], X_R8L, cy)

    # 左侧 QF
    ys_qfl = []
    for i in range(2):
        y = card_y(i, 2); card(X_QFL, y, bracket["QF"][i])
        cy = y + CARD_H // 2; ys_qfl.append(cy)
        connect(X_R8L + COL_W, ys_r8l[i * 2],     X_QFL, cy)
        connect(X_R8L + COL_W, ys_r8l[i * 2 + 1], X_QFL, cy)

    # 右侧 R16
    ys_r16r = []
    for i in range(8):
        y = card_y(i, 8); card(X_R16R, y, bracket["R16"][8 + i])
        ys_r16r.append(y + CARD_H // 2)

    # 右侧 R8(出 R16 左边缘 ← 进 R8 右边缘)
    ys_r8r = []
    for i in range(4):
        y = card_y(i, 4); card(X_R8R, y, bracket["R8"][4 + i])
        cy = y + CARD_H // 2; ys_r8r.append(cy)
        connect(X_R8R + COL_W, cy, X_R16R, ys_r16r[i * 2])
        connect(X_R8R + COL_W, cy, X_R16R, ys_r16r[i * 2 + 1])

    # 右侧 QF
    ys_qfr = []
    for i in range(2):
        y = card_y(i, 2); card(X_QFR, y, bracket["QF"][2 + i])
        cy = y + CARD_H // 2; ys_qfr.append(cy)
        connect(X_QFR + COL_W, cy, X_R8R, ys_r8r[i * 2])
        connect(X_QFR + COL_W, cy, X_R8R, ys_r8r[i * 2 + 1])

    # 中央 SF①
    label(CTR_CARD_X + COL_W // 2, sf_top_y - 18, "半决赛 ①")
    card(CTR_CARD_X, sf_top_y, bracket["SF"][0])
    connect(X_QFL + COL_W, ys_qfl[0], CTR_CARD_X,           sf_top_y + CARD_H // 2)
    connect(CTR_CARD_X + COL_W, sf_top_y + CARD_H // 2, X_QFR, ys_qfr[0])

    # 中央 SF②
    label(CTR_CARD_X + COL_W // 2, sf_bot_y - 18, "半决赛 ②")
    card(CTR_CARD_X, sf_bot_y, bracket["SF"][1])
    connect(X_QFL + COL_W, ys_qfl[1], CTR_CARD_X,           sf_bot_y + CARD_H // 2)
    connect(CTR_CARD_X + COL_W, sf_bot_y + CARD_H // 2, X_QFR, ys_qfr[1])

    # 决赛
    label(CTR_CARD_X + COL_W // 2, fin_y - 18, "🏆 决赛 🏆")
    card(CTR_CARD_X, fin_y, bracket["FINAL"])

    # SF → Final → 冠军条 → 3rd 的纵向连线
    draw.line([(MID_X, sf_top_y + CARD_H), (MID_X, fin_y)],            fill=GOLD, width=2)
    draw.line([(MID_X, sf_bot_y),           (MID_X, fin_y + CARD_H)],   fill=GOLD, width=2)

    # 冠军条(居中)
    fm = bracket["FINAL"]
    champ_text = "冠军待定"
    if fm.get("status") == "FINISHED":
        w = _winner_name(fm)
        if w:
            info = COUNTRY.get(w, {"zh": w, "flag": ""})
            champ_text = f"🏆 {info['flag']} {info['zh']}"
    champ_w = COL_W + 60
    champ_x = CTR_CARD_X + COL_W // 2 - champ_w // 2
    champ_y = fin_y + CARD_H + 30
    draw.rounded_rectangle(
        [champ_x, champ_y, champ_x + champ_w, champ_y + 55],
        10, fill=GOLD)
    safe_emoji_text(
        (champ_x + 30, champ_y + 14),
        champ_text, f_champ, "#0a1f4d")

    # 季军赛
    label(CTR_CARD_X + COL_W // 2, third_y - 18, "季军赛")
    card(CTR_CARD_X, third_y, bracket["3RD"])

    # 页脚
    draw.text((W // 2, H - 30),
              f"更新时间: {datetime.now():%Y-%m-%d %H:%M}  ·  数据源: football-data.org",
              fill=GRAY, font=f_small, anchor="mm")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path)
    print(f"[OK] 已生成 {out_path}")

# ── 主流程 ─────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        with open("data/2026_worldcup_data.json", "r", encoding="utf-8") as f:
            matches = json.load(f)["matches"]
    except FileNotFoundError:
        print("[WARN] data/2026_worldcup_data.json 不存在,使用空数据")
        matches = []

    bracket = build_bracket(matches)
    print(export_text(bracket))
    os.makedirs("output", exist_ok=True)
    render_png(bracket, f"output/wc2026_{datetime.now():%Y%m%d}.png")
