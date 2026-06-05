import json
import datetime
from typing import List, Dict, Any, Optional
from team_flag import team_flag


class WorldCupDataProcessor:
    """
    从 football-data.org 抓取的 JSON 文件中读取、清洗、格式化数据，
    供 Gemini Prompt 和前端 HTML 消费。
    """
    def __init__(self, data_file: str = "data/2026_worldcup_data.json", process_date:  datetime.date = datetime.date.today()):
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except FileNotFoundError:
            print(f"[DataProcessor] Warning: {data_file} not found. Using empty dataset.")
            self.data = {"matches": [], "standings": [], "scorers": []}
        self.today = process_date

    def get_flag_emoji(self,team_name):
        """
        输入国家队中文、英文或简称，自动返回对应的国旗 Emoji 字符。
        如果未找到，则安全返回白色旗帜 🏳 防止脚本崩溃。
        """
        # 1. 匹配 2 位 ISO 国家代码
        country_code = team_flag.get(team_name)
        if not country_code:
            return "🏳"
        
        # 2. 将代码（如 'FR'）安全转换为国旗 Emoji 字符
        try:
            return "".join(chr(ord(char) + 127397) for char in country_code.upper())
        except Exception:
            return "🏳"

    # ──────────────────────────────────────────
    # 比赛查询
    # ──────────────────────────────────────────

    def get_matches_by_date(self, target_date: datetime.date,
                            statuses: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """返回指定日期、指定状态的比赛列表（按开球时间升序）"""
        if statuses is None:
            statuses = ["FINISHED", "IN_PLAY", "PAUSED", "TIMED", "SCHEDULED"]
        date_str = target_date.strftime("%Y-%m-%d")
        result = [
            m for m in self.data.get("matches", [])
            if m.get("utcDate", "")[:10] == date_str
            and m.get("status") in statuses
        ]
        return sorted(result, key=lambda x: x.get("utcDate", ""))

    def get_today_matches(self) -> List[Dict[str, Any]]:
        """今日已完赛 / 进行中 / 暂停的比赛"""
        return self.get_matches_by_date(
            self.today, ["FINISHED", "IN_PLAY", "PAUSED"]
        )

    def get_tomorrow_matches(self) -> List[Dict[str, Any]]:
        """明日已定时 / 计划中的比赛"""
        return self.get_matches_by_date(
            self.today + datetime.timedelta(days=1), ["TIMED", "SCHEDULED"]
        )

    # ──────────────────────────────────────────
    # 射手榜
    # ──────────────────────────────────────────

    def get_top_scorers(self, limit: int = 5) -> List[Dict[str, Any]]:
        """返回进球数前 N 的球员，按进球数降序"""
        scorers = self.data.get("scorers", [])
        sorted_scorers = sorted(
            scorers,
            key=lambda x: (x.get("goals") or 0, -(x.get("penalties") or 0)),
            reverse=True
        )
        return sorted_scorers[:limit]

    # ──────────────────────────────────────────
    # 积分榜
    # ──────────────────────────────────────────

    def get_group_standings(self, group: Optional[str] = None) -> List[Dict[str, Any]]:
        """返回指定小组（或所有小组）的积分榜"""
        standings = self.data.get("standings", [])
        if group:
            return [s for s in standings if s.get("group") == group]
        return standings

    # ──────────────────────────────────────────
    # 格式化辅助
    # ──────────────────────────────────────────

    def format_match_for_display(self, match: Dict[str, Any]) -> Dict[str, Any]:
        """将 API 原始 match 对象转换为展示友好的扁平字典"""
        home = match.get("homeTeam") or {}
        away = match.get("awayTeam") or {}
        score = match.get("score") or {}
        full_time = score.get("fullTime") or {}
        half_time = score.get("halfTime") or {}

        # UTC → 美东时间偏移（夏令时 EDT = UTC-4）
        utc_date = match.get("utcDate", "")
        kickoff_et = ""
        if utc_date:
            try:
                dt_utc = datetime.datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
                dt_et = dt_utc - datetime.timedelta(hours=4)   # EDT
                kickoff_et = dt_et.strftime("%m/%d %H:%M ET")
            except Exception:
                kickoff_et = utc_date

        home_score = full_time.get("home")
        away_score = full_time.get("away")

        return {
            "match_id":   match.get("id"),
            "home_team":  home.get("name", "TBD"),
            "away_team":  away.get("name", "TBD"),
            "home_flag":  home.get("crest", ""),
            "home_emoji": self.get_flag_emoji(home.get("name", "TBD")),
            "away_flag":  away.get("crest", ""),
            "away_emoji": self.get_flag_emoji(away.get("name", "TBD")),
            "home_score": str(home_score) if home_score is not None else "-",
            "away_score": str(away_score) if away_score is not None else "-",
            "ht_home":    str(half_time.get("home", "-")),
            "ht_away":    str(half_time.get("away", "-")),
            "status":     match.get("status", "SCHEDULED"),
            "utc_date":   utc_date,
            "kickoff_et": kickoff_et,
            "venue":      match.get("venue") or "TBD",
            "city":       match.get("area", {}).get("name", ""),
            "group":      match.get("group") or "",
            "stage":      match.get("stage") or "",
            "matchday":   match.get("matchday"),
        }

    def format_scorer_for_display(self, scorer: Dict[str, Any], rank: int) -> Dict[str, Any]:
        """格式化单条射手榜数据"""
        player = scorer.get("player") or {}
        team   = scorer.get("team") or {}
        return {
            "rank":        rank,
            "player_name": player.get("name", "Unknown"),
            "nationality": player.get("nationality", ""),
            "team_name":   team.get("name", ""),
            "team_emoji": self.get_flag_emoji(team.get("name")),
            "goals":       scorer.get("goals") or 0,
            "assists":     scorer.get("assists") or 0,
            "penalties":   scorer.get("penalties") or 0,
            "played_matches": scorer.get("playedMatches") or 0,
        }

    # ──────────────────────────────────────────
    # Gemini 导出接口（主入口）
    # ──────────────────────────────────────────

    def export_for_gemini(self) -> Dict[str, Any]:
        """
        返回结构化摘要，直接注入 Gemini Prompt 占位符。
        包含：今日赛果、明日赛程、射手榜 Top5、小组积分榜摘要。
        """
        today_raw      = self.get_today_matches()
        tomorrow_raw   = self.get_tomorrow_matches()
        scorers_raw    = self.get_top_scorers(5)
        standings_raw  = self.get_group_standings()

        today_matches    = [self.format_match_for_display(m) for m in today_raw]
        tomorrow_matches = [self.format_match_for_display(m) for m in tomorrow_raw]
        top_scorers      = [self.format_scorer_for_display(s, i + 1)
                            for i, s in enumerate(scorers_raw)]

        # 积分榜：只取前 8 组（A-H），每组取前 4 支球队
        standings_sample = []
        for grp in standings_raw[:8]:
            table = grp.get("table") or []
            standings_sample.append({
                "group": grp.get("group", ""),
                "stage": grp.get("stage", ""),
                "type":  grp.get("type", ""),
                "table": [
                    {
                        "position": row.get("position"),
                        "team":     (row.get("team") or {}).get("name", ""),
                        "played":   row.get("playedGames"),
                        "won":      row.get("won"),
                        "draw":     row.get("draw"),
                        "lost":     row.get("lost"),
                        "gf":       row.get("goalsFor"),
                        "ga":       row.get("goalsAgainst"),
                        "gd":       row.get("goalDifference"),
                        "points":   row.get("points"),
                    }
                    for row in table[:4]
                ],
            })

        return {
            "today_date":       self.today.strftime("%Y-%m-%d"),
            "last_updated":     self.data.get("last_updated", ""),
            "today_matches":    today_matches,
            "tomorrow_matches": tomorrow_matches,
            "top_scorers":      top_scorers,
            "standings_sample": standings_sample,
        }
