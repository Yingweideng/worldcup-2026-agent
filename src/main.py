import os
import json
import hashlib
import datetime
import requests
from scrapling import Fetcher
from google import genai
from dotenv import load_dotenv

# 加载本地 .env 密钥
load_dotenv()

# 赛程关键日期
TOURNAMENT_START = datetime.date(2026, 6, 11)
TOURNAMENT_END = datetime.date(2026, 7, 19)

class WorldCupEditor:
    def __init__(self):
        self.today = datetime.date.today()
        self.today_str = self.today.strftime("%Y-%m-%d")
        # 新增：用于存储动态生成的仪式感标题        
        self.dynamic_title = ""         
        self.db_path = "data/processed_urls.json"
        self.history_dir = "history"

        self.config = self._load_json("config/sources.json")
        self.prompt_template = self._load_file("templates/gemini_prompt.md")
        self.web_template = self._load_file("templates/web_template.html")
        self.index_template = self._load_file("templates/index_template.html")

        self.processed_urls = self._load_database()
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    def _load_json(self, path):
        with open(path, "r", encoding="utf-8") as f: return json.load(f)

    def _load_file(self, path):
        with open(path, "r", encoding="utf-8") as f: return f.read()

    def _load_database(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if os.path.exists(self.db_path):
            try: return set(self._load_json(self.db_path))
            except: return set()
        return set()

    def _save_database(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(list(self.processed_urls), f, ensure_ascii=False, indent=2)

    def _get_phase(self):
        if self.today < TOURNAMENT_START:
            days_left = (TOURNAMENT_START - self.today).days
            self.dynamic_title = f"2026 美加墨世界杯 倒计时 {days_left} 天"
            return {"phase": "PRE", "label": "赛前备战模式", "blocks": "news_feed, feature, schedule"}
        elif self.today <= TOURNAMENT_END:
            day_num = (self.today - TOURNAMENT_START).days + 1            
            self.dynamic_title = f"2026 美加墨世界杯 第 {day_num} 比赛日"            
            return {"phase": "IN", "label": "比赛日模式", "blocks": "feature, match_list, ranking, schedule, news_feed"}
        return {"phase": "POST", "label": "赛后总结模式", "blocks": "feature, ranking, news_feed"}

    def fetch_raw_news(self):
        articles = []
        for url in self.config.get("tier1_sources", []):
            try:
                page = Fetcher.get(url)
                for link in page.css("a"):
                    href = link.attrib.get("href", "")
                    text = link.text.strip() if link.text else ""
                    if href.startswith("/") and not href.startswith("//"):
                        href = "/".join(url.split("/")[:3]) + href
                    if any(kw in href.lower() or kw in text.lower() for kw in ["world-cup", "2026", "fifa", "match"]):
                        url_hash = hashlib.md5(href.encode("utf-8")).hexdigest()
                        if url_hash not in self.processed_urls:
                            articles.append({"title": text, "url": href, "hash": url_hash})
            except Exception as e: print(f"Error fetching {url}: {e}")
        return articles

    def fetch_stats_data(self):
        try: return Fetcher.get(self.config.get("stats_source", "")).text[:15000]
        except: return ""

    def generate_report(self, news, stats):
        phase = self._get_phase()
        prompt = self.prompt_template.format(
            today_str=self.today_str, phase_label=phase["label"],
            recommended_blocks=phase["blocks"], news_items=json.dumps(news, ensure_ascii=False),
            stats_text=stats or "无"
        )
        return self.client.models.generate_content(model="gemini-3.5-flash", contents=prompt).text

    def _extract_json(self, raw):
        s, e = raw.find("<!--DATA_START-->"), raw.find("<!--DATA_END-->")
        if s != -1 and e != -1: return raw[s+17:e].strip()
        return None

    def build_telegram_text(self, data):
        emoji = {"feature": "🏆", "match_list": "📊", "ranking": "⚽", "schedule": "📅", "news_feed": "📰"}
        parts = [f"<b>📢 {self.dynamic_title}</b>\n"] 
        #parts = []
        for b in data.get("blocks", []):
            t, title = b.get("type"), b.get("title", "情报")
            parts.append(f"<b>{emoji.get(t, '•')} {title}</b>")
            items = b.get("items", [])
            if t == "feature":
                score = b.get("score")
                header = f"{b.get('home')} {score} {b.get('away')}\n" if score else ""
                parts.append(f"<blockquote>{header}{b.get('content','')}</blockquote>")
            elif t == "news_feed":
                lines = [f"• [{n.get('tag','新闻')}] {n.get('text')} <a href='{n.get('url')}'>详情</a>" for n in items]
                parts.append(f"<blockquote>{'\n'.join(lines)}</blockquote>")
        return "\n\n".join(parts)

    def send_to_telegram(self, html_content):
        """补全：推送 HTML 内容到 Telegram"""
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            print("Telegram credentials missing.")
            return False
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": html_content, "parse_mode": "HTML", "disable_web_page_preview": False}
        try:
            r = requests.post(url, json=payload)
            r.raise_for_status()
            print("Successfully sent message to Telegram.")
            return True
        except Exception as e:
            print(f"Failed to send Telegram message: {e}")
            return False

    def save_and_build_history(self, json_str):
        os.makedirs(self.history_dir, exist_ok=True)
        html = self.web_template.replace("{today_str}", self.today_str).replace("{dynamic_title}", self.dynamic_title).replace("{data_json}", json_str)
        with open(os.path.join(self.history_dir, f"{self.today_str}.html"), "w", encoding="utf-8") as f:
            f.write(html)
        self.rebuild_index_html()

    def rebuild_index_html(self):
        files = sorted([f for f in os.listdir(self.history_dir) if f.endswith(".html") and f != "index.html"], reverse=True)
        items = "".join([f'<li><a href="{f}"><span class="date-text">{f.replace(".html","")} 日报</span></a></li>' for f in files])
        with open(os.path.join(self.history_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(self.index_template.replace("{list_items}", items or "暂无归档"))

    def run(self):
        print(f"Starting Agent... Date: {self.today_str}")
        news, stats = self.fetch_raw_news(), self.fetch_stats_data()
        if not news and not stats: 
            print("No data found.")
            return
        
        raw = self.generate_report(news, stats)
        json_str = self._extract_json(raw)
        if json_str:
            try:
                data = json.loads(json_str)
                # 关键：调用补全后的 send_to_telegram
                self.send_to_telegram(self.build_telegram_text(data))
                for n in news: self.processed_urls.add(n["hash"])
                self._save_database()
                self.save_and_build_history(json_str)
                print("Task completed.")
            except Exception as e:
                print(f"Error in run loop: {e}")
        else:
            print("Failed to extract JSON from AI response.")

if __name__ == "__main__": 
    WorldCupEditor().run()
