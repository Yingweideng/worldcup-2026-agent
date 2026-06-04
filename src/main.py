import os
import json
import hashlib
import datetime
import time
import requests
from scrapling import Fetcher
from google import genai
from dotenv import load_dotenv
from data_processor import WorldCupDataProcessor

# 加载本地 .env 密钥
load_dotenv()

# 赛程关键日期
TOURNAMENT_START = datetime.date(2026, 6, 11)
TOURNAMENT_END   = datetime.date(2026, 7, 19)


class WorldCupEditor:
    def __init__(self):
        self.today      = datetime.date.today()
        #self.today      = datetime.date(2026, 6, 14)
        self.today_str  = self.today.strftime("%Y-%m-%d")
        self.dynamic_title = ""

        self.db_path     = "data/processed_urls.json"
        self.history_dir = "history"
        self.output_file = "data/2026_worldcup_data.json"

        self.config          = self._load_json("config/sources.json")
        self.prompt_template = self._load_file("templates/gemini_prompt.md")
        self.web_template    = self._load_file("templates/web_template.html")
        self.index_template  = self._load_file("templates/index_template.html")

        self.processed_urls = self._load_database()
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

        # football-data.org API 配置
        self.football_base_url = "https://api.football-data.org/v4/competitions/WC"
        self.football_headers  = {"X-Auth-Token": os.environ.get("FOOTBALL_DATA_API_TOKEN", "")}

        # 数据处理器（若 JSON 不存在则为 None，fallback 到空数据）
        self.data_processor = self._init_data_processor()

    # ──────────────────────────────────────────
    # 初始化辅助
    # ──────────────────────────────────────────

    def _init_data_processor(self) -> "WorldCupDataProcessor | None":
        if os.path.exists(self.output_file):
            return WorldCupDataProcessor(self.output_file, self.today)
        print("[main] Warning: 2026_worldcup_data.json not found — will fetch first.")
        return None

    def _load_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _load_database(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if os.path.exists(self.db_path):
            try:
                return set(self._load_json(self.db_path))
            except Exception:
                return set()
        return set()

    def _save_database(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(list(self.processed_urls), f, ensure_ascii=False, indent=2)

    # ──────────────────────────────────────────
    # 赛事阶段判断
    # ──────────────────────────────────────────

    def _get_phase(self):
        if self.today < TOURNAMENT_START:
            days_left = (TOURNAMENT_START - self.today).days
            self.dynamic_title = f"2026 美加墨世界杯 倒计时 {days_left} 天"
            return {
                "phase": "PRE",
                "label": "赛前备战模式",
                "blocks": "news_feed, feature, schedule"
            }
        elif self.today <= TOURNAMENT_END:
            day_num = (self.today - TOURNAMENT_START).days + 1
            self.dynamic_title = f"2026 美加墨世界杯 第 {day_num} 比赛日"
            return {
                "phase": "IN",
                "label": "比赛日模式",
                "blocks": "feature, match_list, ranking, schedule, news_feed"
            }
        self.dynamic_title = "2026 美加墨世界杯 赛后回顾"
        return {
            "phase": "POST",
            "label": "赛后总结模式",
            "blocks": "feature, ranking, news_feed"
        }

    # ──────────────────────────────────────────
    # 数据抓取
    # ──────────────────────────────────────────

    def _football_fetch(self, endpoint):
        """请求 football-data.org 单个 endpoint"""
        url = f"{self.football_base_url}/{endpoint}"
        try:
            resp = requests.get(url, headers=self.football_headers, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"[football-data] Error fetching /{endpoint}: {e}")
            return None

    def fetch_results_data(self):
        """从 football-data.org 拉取 matches / standings / scorers 并写入 JSON"""
        print("[football-data] Starting fetch: matches, standings, scorers …")

        matches_data   = self._football_fetch("matches")
        time.sleep(6)
        standings_data = self._football_fetch("standings")
        time.sleep(6)
        scorers_data   = self._football_fetch("scorers")

        combined = {
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "competition":  {"name": "FIFA World Cup 2026", "code": "WC"},
            "matches":   (matches_data  or {}).get("matches",   []),
            "standings": (standings_data or {}).get("standings", []),
            "scorers":   (scorers_data   or {}).get("scorers",   []),
        }

        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)

        print(f"[football-data] Data saved → {self.output_file}")

        # 刷新处理器，使本次 run() 后续步骤立即可用
        self.data_processor = WorldCupDataProcessor(self.output_file, self.today)

    def fetch_raw_news(self):
        """从 Tier-1 来源抓取世界杯相关新闻链接"""
        articles = []
        keywords = ["world-cup", "2026", "fifa", "match", "世界杯", "美加墨世界杯", "2026世界杯"]
        for url in self.config.get("tier1_sources", []):
            try:
                page = Fetcher.get(url)
                for link in page.css("a"):
                    href = link.attrib.get("href", "")
                    text = (link.text or "").strip()
                    if href.startswith("/") and not href.startswith("//"):
                        href = "/".join(url.split("/")[:3]) + href
                    if any(kw in href.lower() or kw in text.lower() for kw in keywords):
                        url_hash = hashlib.md5(href.encode("utf-8")).hexdigest()
                        if url_hash not in self.processed_urls:
                            articles.append({"title": text, "url": href, "hash": url_hash})
            except Exception as e:
                print(f"[scraper] Error fetching {url}: {e}")
        return articles

    def fetch_stats_data(self):
        try:
            return Fetcher.get(self.config.get("stats_source", "")).text[:15000]
        except Exception:
            return ""

    # ──────────────────────────────────────────
    # AI 生成
    # ──────────────────────────────────────────

    def generate_report(self, news: list, stats: str) -> str:
        """构造 Prompt 并调用 Gemini，返回原始文本（含 JSON）

        ⚠️  修复说明：原先使用 str.format() 会把模板中 JSON 示例里的
            {  }  花括号（如 {"blocks": [...]}）误解析为占位符，
            导致 KeyError。改用逐一 str.replace() 替换具名占位符，
            完全绕开这一问题。
        """
        phase = self._get_phase()

        # 官方数据注入（若处理器可用则导出，否则给空占位）
        if self.data_processor:
            wc = self.data_processor.export_for_gemini()
        else:
            wc = {
                "today_matches":    [],
                "tomorrow_matches": [],
                "top_scorers":      [],
                "standings_sample": [],
            }

        #print(json.dumps(wc["today_matches"]))
        #print(json.dumps(wc["tomorrow_matches"]))
        #print(json.dumps(wc["top_scorers"]))
        #print(json.dumps(wc["standings_sample"]))        
        
        # ── 使用 str.replace() 逐一替换，避免 str.format() 误解析 JSON 花括号 ──
        prompt = (
            self.prompt_template
            .replace("{today_str}",          self.today_str)
            .replace("{phase_label}",         phase["label"])
            .replace("{recommended_blocks}",  phase["blocks"])
            .replace("{news_items}",          json.dumps(news,                    ensure_ascii=False))
            .replace("{stats_text}",          stats or "无")
            .replace("{worldcup_matches}",    json.dumps(wc["today_matches"],    ensure_ascii=False))
            .replace("{tomorrow_matches}",    json.dumps(wc["tomorrow_matches"], ensure_ascii=False))
            .replace("{top_scorers}",         json.dumps(wc["top_scorers"],      ensure_ascii=False))
            .replace("{standings}",           json.dumps(wc["standings_sample"], ensure_ascii=False))
        )

        response = self.client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
        )
        return response.text

    # ──────────────────────────────────────────
    # 输出构建
    # ──────────────────────────────────────────

    def _extract_json(self, raw: str):
        s = raw.find("<!--DATA_START-->")
        e = raw.find("<!--DATA_END-->")
        if s != -1 and e != -1:
            return raw[s + 17:e].strip()
        return None

    def build_telegram_text(self, data: dict) -> str:
        emoji_map = {
            "feature":    "🏆",
            "match_list": "📊",
            "ranking":    "⚽",
            "schedule":   "📅",
            "news_feed":  "📰",
        }
        parts = [f"<b>📢 {self.dynamic_title}</b>\n"]

        for b in data.get("blocks", []):
            btype = b.get("type", "")
            title = b.get("title", "情报")
            icon  = emoji_map.get(btype, "•")
            parts.append(f"<b>{icon} 【{title}】</b>")

            if btype == "feature":
                score  = b.get("score")
                header = f" <b>{b.get('home')} {score} {b.get('away')}</b> \n" if score else ""
                parts.append(f"<blockquote>{header}{b.get('content','')}</blockquote>")

            elif btype == "match_list":
                lines = []
                for m in b.get("items", []):
                    score_str = f"{m.get('home_score','-')} : {m.get('away_score','-')}"
                    line = (
                        f" <b>{m.get('home_team')}</b> {score_str} "
                        f"<b>{m.get('away_team')}</b> "
                    )
                    #if m.get("venue"):
                    #    line += f"  🏟 {m['venue']}"
                    if m.get("group"):
                        line += f"  [{m['group']}]"
                    lines.append(line)
                parts.append("<blockquote>" + "\n".join(lines) + "</blockquote>")

            elif btype == "schedule":
                lines = []
                for m in b.get("items", []):
                    lines.append(
                        f" <b>{m.get('home_team')}</b> vs <b>{m.get('away_team')}</b> "
                        f"  {m.get('kickoff_et','TBD')}"
                        + (f"  [{m.get('group','')}]" if m.get("group") else "")
                    )
                parts.append("<blockquote>" + "\n".join(lines) + "</blockquote>")

            elif btype == "ranking":
                lines = []
                for r in b.get("items", []):
                    lines.append(
                        f"{r.get('rank','#')}. <b>{r.get('player_name')}</b>"
                        f"({r.get('team_name','')}) ｜ ⚽ {r.get('goals',0)}"
                        + (f" (点球 {r['penalties']})" if r.get("penalties") else "")
                    )
                parts.append("<blockquote>" + "\n".join(lines) + "</blockquote>")

            elif btype == "news_feed":
                lines = [
                    f"• [{n.get('tag','新闻')}] {n.get('text')} "
                    f"<a href='{n.get('url','#')}'>详情</a>"
                    for n in b.get("items", [])
                ]
                parts.append("<blockquote>" + "\n".join(lines) + "</blockquote>")

        return "\n\n".join(parts)

    def send_to_telegram(self, html_content: str) -> bool:
        token   = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")

        #temprary code
        tele_out_path = os.path.join(self.history_dir, f"tele_{self.today_str}.html")
        with open(tele_out_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        if not token or not chat_id:
            print("[telegram] Credentials missing — skipping send.")
            return False
        url     = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id":                  chat_id,
            "text":                     html_content,
            "parse_mode":               "HTML",
            "disable_web_page_preview": False,
        }
        try:
            r = requests.post(url, json=payload, timeout=15)
            r.raise_for_status()
            print("[telegram] Message sent successfully.")
            return True
        except Exception as e:
            print(f"[telegram] Failed: {e}")
            return False

    def save_and_build_history(self, json_str: str):
        os.makedirs(self.history_dir, exist_ok=True)
        html = (
            self.web_template
            .replace("{today_str}",     self.today_str)
            .replace("{dynamic_title}", self.dynamic_title)
            .replace("{data_json}",     json_str)
        )
        out_path = os.path.join(self.history_dir, f"{self.today_str}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[history] Saved → {out_path}")
        self.rebuild_index_html()

    def rebuild_index_html(self):
        files = sorted(
            [f for f in os.listdir(self.history_dir)
             if f.endswith(".html") and f != "index.html"],
            reverse=True,
        )
        items = []
        for f in files:
            date_part = f.replace(".html", "")
            items.append(
                f'<li><a href="{f}">'
                f'<span class="date-text">{date_part} 世界杯情报日报</span>'
                f'</a></li>'
            )
        list_items = "\n".join(items) if items else (
            '<div class="empty">暂无历史日报，系统将每日自动生成归档。</div>'
        )
        index_html = self.index_template.replace("{list_items}", list_items)
        with open(os.path.join(self.history_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(index_html)
        print("[history] index.html rebuilt.")

    # ──────────────────────────────────────────
    # 主入口
    # ──────────────────────────────────────────

    def run(self):
        print(f"[agent] Starting … Date: {self.today_str}")

        # Step 1: 从 football-data.org 拉取官方数据（写入 JSON 并刷新处理器）
        #self.fetch_results_data()

        # Step 2: 从网络抓取新闻 + 统计文本
        news  = self.fetch_raw_news()
        stats = self.fetch_stats_data()

        if not news and not stats and not self.data_processor:
            print("[agent] No data at all — aborting.")
            return

        # Step 3: Gemini 生成报告
        raw      = self.generate_report(news, stats)
        json_str = self._extract_json(raw)

        if json_str:
            try:
                data = json.loads(json_str)
                # Step 4: 推送 Telegram
                self.send_to_telegram(self.build_telegram_text(data))
                # Step 5: 标记已处理 URL
                for n in news:
                    self.processed_urls.add(n["hash"])
                self._save_database()
                # Step 6: 写入历史 HTML + 重建归档首页
                self.save_and_build_history(json_str)
                print("[agent] ✅ Task completed successfully.")
            except Exception as e:
                print(f"[agent] ❌ Error in run loop: {e}")
        else:
            print("[agent] ❌ Failed to extract JSON from AI response.")
            print("── Raw output ──────────────────────────")
            print(raw[:2000])


if __name__ == "__main__":
    WorldCupEditor().run()
