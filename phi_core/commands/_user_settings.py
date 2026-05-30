from __future__ import annotations

from typing import Any

USER_SETTING_META: dict[str, dict[str, str]] = {
    "theme": {
        "title": "主题风格",
        "description": "使用 phi myset theme <序号> 修改，控制图片页面的整体视觉风格。",
    },
    "b30AvgKind": {
        "title": "B30统计数据展示",
        "description": "控制 B30 均值条展示的数据范围，可按全部、B30、Top 或隐藏展示。",
    },
    "b30AvgColor": {
        "title": "B30均值条配色",
        "description": "控制 B30 均值条主色，用于快速区分展示偏好。",
    },
    "allowApiUsage": {
        "title": "API功能开关",
        "description": "关闭后将尽量不使用在线查分平台相关功能。",
    },
}

USER_SETTING_OPTIONS: dict[str, dict[str, dict[str, str]]] = {
    "theme": {
        "default": {"title": "[0]默认", "description": "使用基础主题和随机曲绘背景。"},
        "snow": {"title": "[1]寒冬", "description": "在默认视觉上加入落雪主题元素。"},
        "star": {"title": "[2]使一颗心免于哀伤", "description": "使用星空主题视觉。"},
        "dss2": {"title": "[3]大师赛2", "description": "使用 Phigros 大师赛第二赛季主题配色。"},
    },
    "b30AvgKind": {
        "all": {"title": "[0]全部统计", "description": "展示相近 RKS 玩家全部成绩平均值统计。"},
        "b30": {"title": "[1]仅 B30", "description": "仅按 B30 成绩平均值展示统计。"},
        "top": {"title": "[2]仅 Top", "description": "展示玩家成绩在相近 RKS 玩家中的百分比位置。"},
        "none": {"title": "[3]隐藏", "description": "不展示 B30 均值相关信息。"},
    },
    "b30AvgColor": {
        "red": {"title": "[0]红", "description": "高对比暖色方案。"},
        "gold": {"title": "[1]金", "description": "偏亮金色，强调成就感。"},
        "blue": {"title": "[2]蓝", "description": "冷色调方案，信息阅读更平稳。"},
        "green": {"title": "[3]绿", "description": "中性偏亮配色，整体观感更清新。"},
    },
    "allowApiUsage": {
        "true": {"title": "[0]启用", "description": "允许使用在线查分平台相关能力。"},
        "false": {"title": "[1]禁用", "description": "禁用在线查分平台能力，仅使用本地数据。"},
    },
}

SETTING_KEY_ALIASES: dict[str, str] = {
    "theme": "theme",
    "主题": "theme",
    "主题风格": "theme",
    "b30avgkind": "b30AvgKind",
    "b30kind": "b30AvgKind",
    "avgkind": "b30AvgKind",
    "均值范围": "b30AvgKind",
    "统计范围": "b30AvgKind",
    "均值类型": "b30AvgKind",
    "b30avgcolor": "b30AvgColor",
    "avgcolor": "b30AvgColor",
    "颜色": "b30AvgColor",
    "配色": "b30AvgColor",
    "均值颜色": "b30AvgColor",
    "api": "allowApiUsage",
    "allowapiusage": "allowApiUsage",
    "api开关": "allowApiUsage",
    "api功能": "allowApiUsage",
    "api功能开关": "allowApiUsage",
    "在线api": "allowApiUsage",
}

SETTING_VALUE_ALIASES: dict[str, dict[str, str]] = {
    "theme": {
        "default": "default",
        "snow": "snow",
        "star": "star",
        "dss2": "dss2",
        "默认": "default",
        "寒冬": "snow",
        "星空": "star",
        "使一颗心免于哀伤": "star",
        "大师赛2": "dss2",
    },
    "b30AvgKind": {
        "all": "all",
        "b30": "b30",
        "top": "top",
        "none": "none",
        "全部": "all",
        "全部统计": "all",
        "仅b30": "b30",
        "仅top": "top",
        "隐藏": "none",
        "关": "none",
    },
    "b30AvgColor": {
        "red": "red",
        "gold": "gold",
        "blue": "blue",
        "green": "green",
        "红": "red",
        "红色": "red",
        "金": "gold",
        "金色": "gold",
        "蓝": "blue",
        "蓝色": "blue",
        "绿": "green",
        "绿色": "green",
    },
    "allowApiUsage": {
        "true": "true",
        "false": "false",
        "on": "true",
        "off": "false",
        "开": "true",
        "关": "false",
        "开启": "true",
        "关闭": "false",
        "允许": "true",
        "禁止": "false",
        "启用": "true",
        "禁用": "false",
        "是": "true",
        "否": "false",
        "1": "true",
        "0": "false",
    },
}

DEFAULT_USER_SETTINGS: dict[str, Any] = {
    "theme": "default",
    "b30AvgKind": "all",
    "b30AvgColor": "red",
    "allowApiUsage": True,
}


def normalize_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    settings = dict(DEFAULT_USER_SETTINGS)
    if raw:
        settings.update(raw)
    settings["allowApiUsage"] = settings.get("allowApiUsage") is not False
    for key in ("theme", "b30AvgKind", "b30AvgColor"):
        value = str(settings.get(key) or DEFAULT_USER_SETTINGS[key])
        if value not in USER_SETTING_OPTIONS[key]:
            value = str(DEFAULT_USER_SETTINGS[key])
        settings[key] = value
    return settings


def build_setting_panel_data(settings: dict[str, Any]) -> dict[str, Any]:
    current = normalize_settings(settings)
    return {
        "pageTitle": "Phi-Plugin 用户设置",
        "pageDescription": "以下选项为你的个人偏好展示，选择结果将用于对应图片渲染。",
        "items": [
            _build_item("theme", str(current["theme"])),
            _build_item("b30AvgKind", str(current["b30AvgKind"])),
            _build_item("b30AvgColor", str(current["b30AvgColor"])),
            _build_item("allowApiUsage", str(current["allowApiUsage"]).lower()),
        ],
    }


def parse_setting_update(args: str) -> tuple[str, str] | tuple[None, str]:
    normalized = (args or "").replace("：", " ").replace(":", " ").replace("=", " ")
    parts = [part for part in normalized.split() if part]
    if not parts:
        return None, ""
    if len(parts) < 2:
        return None, _usage("参数不足，请提供“设置项 + 目标值”。")
    key = SETTING_KEY_ALIASES.get(parts[0].casefold())
    if key is None:
        return None, _usage(f"未知设置项：{parts[0]}")

    raw_value = "".join(parts[1:])
    option_keys = list(USER_SETTING_OPTIONS[key])
    if raw_value.isdigit():
        index = int(raw_value)
        if 0 <= index < len(option_keys):
            return key, option_keys[index]
    value = SETTING_VALUE_ALIASES[key].get(raw_value.casefold()) or SETTING_VALUE_ALIASES[key].get(raw_value) or raw_value
    if value not in USER_SETTING_OPTIONS[key]:
        optional_values = " / ".join(f"{index}. {name}" for index, name in enumerate(option_keys))
        return None, f"无效值：{raw_value}\n{USER_SETTING_META[key]['title']} 可选：{optional_values}"
    return key, value


def setting_success_message(key: str, value: str) -> str:
    option = USER_SETTING_OPTIONS[key][value]
    return f"设置成功：{USER_SETTING_META[key]['title']} -> {option['title']}"


def _build_item(key: str, current: str) -> dict[str, Any]:
    options = USER_SETTING_OPTIONS[key]
    return {
        "key": key,
        "title": USER_SETTING_META[key]["title"],
        "description": USER_SETTING_META[key]["description"],
        "currentTitle": options.get(current, {}).get("title", current),
        "options": [
            {
                "value": value,
                "title": option["title"],
                "description": option["description"],
                "selected": value == current,
            }
            for value, option in options.items()
        ],
    }


def _usage(prefix: str) -> str:
    return "\n".join(
        [
            prefix,
            "用法示例：",
            "phi myset",
            "phi myset 主题 star",
            "phi myset 主题 3",
            "phi myset 均值范围 b30",
            "phi myset 配色 gold",
            "phi myset API开关 关闭",
        ]
    )
