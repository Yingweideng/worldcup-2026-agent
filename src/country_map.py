"""
2026 世界杯 - 球队名称映射表
英文队名 → 中文名 + 国旗 Emoji
"""

COUNTRY = {
    "Germany":                {"zh": "德国",      "flag": "🇩🇪"},
    "Paraguay":               {"zh": "巴拉圭",    "flag": "🇵🇾"},
    "France":                 {"zh": "法国",      "flag": "🇫🇷"},
    "Sweden":                 {"zh": "瑞典",      "flag": "🇸🇪"},
    "South Africa":           {"zh": "南非",      "flag": "🇿🇦"},
    "Canada":                 {"zh": "加拿大",    "flag": "🇨🇦"},
    "Netherlands":            {"zh": "荷兰",      "flag": "🇳🇱"},
    "Morocco":                {"zh": "摩洛哥",    "flag": "🇲🇦"},
    "Colombia":               {"zh": "哥伦比亚",  "flag": "🇨🇴"},
    "Croatia":                {"zh": "克罗地亚",  "flag": "🇭🇷"},
    "Spain":                  {"zh": "西班牙",    "flag": "🇪🇸"},
    "Austria":                {"zh": "奥地利",    "flag": "🇦🇹"},
    "United States":          {"zh": "美国",      "flag": "🇺🇸"},
    "USA":                    {"zh": "美国",      "flag": "🇺🇸"},
    "Bosnia-Herzegovina":     {"zh": "波黑",      "flag": "🇧🇦"},
    "Belgium":                {"zh": "比利时",    "flag": "🇧🇪"},
    "Korea Republic":         {"zh": "韩国",      "flag": "🇰🇷"},
    "South Korea":            {"zh": "韩国",      "flag": "🇰🇷"},
    "Brazil":                 {"zh": "巴西",      "flag": "🇧🇷"},
    "Japan":                  {"zh": "日本",      "flag": "🇯🇵"},
    "Ivory Coast":            {"zh": "科特迪瓦",  "flag": "🇨🇮"},
    "Cote d'Ivoire":          {"zh": "科特迪瓦",  "flag": "🇨🇮"},
    "Norway":                 {"zh": "挪威",      "flag": "🇳🇴"},
    "Mexico":                 {"zh": "墨西哥",    "flag": "🇲🇽"},
    "Ecuador":                {"zh": "厄瓜多尔",  "flag": "🇪🇨"},
    "England":                {"zh": "英格兰",    "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    "Senegal":                {"zh": "塞内加尔",  "flag": "🇸🇳"},
    "Argentina":              {"zh": "阿根廷",    "flag": "🇦🇷"},
    "Cape Verde":             {"zh": "佛得角",    "flag": "🇨🇻"},
    "Australia":              {"zh": "澳大利亚",  "flag": "🇦🇺"},
    "Egypt":                  {"zh": "埃及",      "flag": "🇪🇬"},
    "Switzerland":            {"zh": "瑞士",      "flag": "🇨🇭"},
    "Iran":                   {"zh": "伊朗",      "flag": "🇮🇷"},
    "Portugal":               {"zh": "葡萄牙",    "flag": "🇵🇹"},
    "Ghana":                  {"zh": "加纳",      "flag": "🇬🇭"},
}

def lookup(name_en: str) -> dict:
    """返回 {'zh': '...', 'flag': '...'}, 未找到时用英文原名兜底"""
    return COUNTRY.get(name_en, {"zh": name_en, "flag": "🏳"})
