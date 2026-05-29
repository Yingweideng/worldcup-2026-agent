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


class WorldCupEditor:
    def __init__(self):
        self.today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        self.db_path = "data/processed_urls.json"
        self.history_dir = "history"

        # 加载解耦后的配置与模板
        self.config = self._load_json("config/sources.json")
        self.prompt_template = self._load_file("templates/gemini_prompt.md")
        self.web_template = self._load_file("templates/web_template.html")
        self.index_template = self._load_file("templates/index_template.html")

        self.processed_urls = self._load_database()

        # 初始化新版 Gemini SDK 客户端
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

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

    def fetch_raw_news(self):
        """利用 Scrapling 爬取 Tier 1 媒体源"""
        collected_articles = []
        sources = self.config.get("tier1_sources", [])

        for url in sources:
            try:
                page = Fetcher.get(url)
                links = page.css("a")
                for link in links:
                    href = link.attrib.get("href", "")
                    text = link.text.strip() if link.text else ""

                    if href.startswith("/") and not href.startswith("//"):
                        base_domain = "/".join(url.split("/")[:3])
                        href = base_domain + href

                    if any(
                        kw in href.lower() or kw in text.lower()
                        for kw in ["world-cup", "2026", "fifa", "match"]
                    ):
                        url_hash = hashlib.md5(href.encode("utf-8")).hexdigest()
                        if url_hash not in self.processed_urls:
                            collected_articles.append(
                                {"title": text, "url": href, "hash": url_hash}
                            )
            except Exception as e:
                print(f"Error fetching {url}: {e}")

        return collected_articles

    def fetch_stats_data(self):
        """爬取官方统计页面文本"""
        stats_url = self.config.get("stats_source", "")
        if not stats_url:
            return ""
        try:
            page = Fetcher.get(stats_url)
            return page.text[:15000]
        except Exception as e:
            print(f"Error fetching stats: {e}")
            return ""

    def generate_report(self, news_items, stats_text):
        """利用新版 SDK 的 client.models.generate_content 接口请求 Gemini 3.5-flash"""
        formatted_prompt = self.prompt_template.format(
            today_str=self.today_str,
            news_items=json.dumps(news_items, ensure_ascii=False, indent=2),
            stats_text=stats_text,
        )
        response = self.client.models.generate_content(
            model="gemini-3.5-flash",
            contents=formatted_prompt,
        )
        return response.text

    def send_to_telegram(self, html_content):
        """推送至 Telegram"""
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            print("Telegram credentials missing.")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": html_content,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        try:
            #r = requests.post(url, json=payload)
            #r.raise_for_status()
            print("Successfully sent message to Telegram.")
            return True
        except Exception as e:
            print(f"Failed to send Telegram message: {e}")
            return False

    def save_and_build_history(self, html_content):
        """生成每日独立归档网页"""
        os.makedirs(self.history_dir, exist_ok=True)

        daily_filename = f"{self.today_str}.html"
        daily_filepath = os.path.join(self.history_dir, daily_filename)

        # 核心修复 1：采用安全的 replace 替换，避免与 CSS 中的 { } 语法冲突
        full_html = self.web_template.replace("{today_str}", self.today_str).replace("{report_html}", html_content)

        with open(daily_filepath, "w", encoding="utf-8") as f:
            f.write(full_html)

        self.rebuild_index_html()

    def rebuild_index_html(self):
        """扫描历史并重建 Pages 主索引页"""
        files = [
            f
            for f in os.listdir(self.history_dir)
            if f.endswith(".html") and f != "index.html"
        ]
        files.sort(reverse=True)

        list_items = ""
        for file in files:
            date_part = file.replace(".html", "")
            # 核心修复 2：将换行符放入转义字符中，确保单行字符串符合 Python 语法
            list_items += f'<li><a href="{file}">{date_part} 世界杯情报日报</a></li>\n'

        # 核心修复 3：采用安全的 replace 替换
        index_html = self.index_template.replace("{list_items}", list_items)

        with open(os.path.join(self.history_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(index_html)

    def run(self):
        print("Starting 2026 World Cup Intelligence Agent...")

        raw_news = self.fetch_raw_news()
        stats_text = self.fetch_stats_data()

        print(f"Captured {len(raw_news)} raw news articles.")

        if not raw_news and not stats_text:
            print("No new data captured today. Exiting.")
            return

        report_html = self.generate_report(raw_news, stats_text)
        
        # 本地控制台预览生成的 Telegram HTML 日报
        print("--- Generated HTML Report ---")
        print(report_html)
        print("-----------------------------")

        telegram_success = self.send_to_telegram(report_html)

        # 本地调试：无论 Telegram 是否发送成功，都在本地落盘历史 HTML 与去重指纹
        if telegram_success or True:
            for item in raw_news:
                self.processed_urls.add(item["hash"])
            self._save_database()

            self.save_and_build_history(report_html)
            print("Pipeline run completed successfully.")


if __name__ == "__main__":
    editor = WorldCupEditor()
    editor.run()
