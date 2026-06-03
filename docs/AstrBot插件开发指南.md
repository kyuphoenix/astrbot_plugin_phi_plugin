---
name: astrbot-plugin-dev
description: AstrBot QQ机器人插件开发指南 - 基于20+真实插件总结的完整规范
tags: [astrbot, qq-bot, plugin, onebot, aiocqhttp, python]
---

# AstrBot 插件开发完整指南

## 一、插件目录结构

每个插件为一个文件夹，典型结构如下：

```
插件名/
├── main.py                # 必需：主入口，包含继承 Star 的类
├── metadata.yaml          # 必需：插件元信息
├── _conf_schema.json      # 可选：配置面板 schema（有配置时必需）
├── README.md              # 可选：说明文档
├── CHANGELOG.md           # 可选：更新日志
├── requirements.txt       # 可选：额外 Python 依赖
├── logo.png               # 可选：插件图标
└── xxx.py                 # 可选：辅助模块（如 Tools.py）
```

**插件路径**：
`~/AstrBot/data/plugins/`

---

## 二、metadata.yaml

```yaml
name: 插件名                    # 必需，唯一标识
display_name: 显示名             # 可选，后台展示名
desc: 插件描述                   # 简短描述
version: v1.0.0                 # 版本号
author: 作者名                   # 作者
repo: https://github.com/...    # 仓库地址（可为"无"）
dependencies: []                # 可选，依赖的其他插件名称
support_platforms:              # 可选，限制平台；不填则支持所有
  - aiocqhttp                  # 仅支持 OneBot 协议（NapCat等）
```

---

## 三、main.py 核心结构

### 3.1 类定义

```python
from astrbot.api.event import filter
from astrbot.api.all import Star, Context, AstrBotConfig, logger

class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        # 读取配置（如有）
        self.some_value = config.get("key", default_value)

    async def initialize(self) -> None:
        """可选异步初始化"""

    async def terminate(self) -> None:
        """当插件被禁用、重载时调用，可用于清理任务、保存数据"""
```

**注意**：
- 如果有 `_conf_schema.json`，则 `__init__` 签名必须为 `(self, context, config)`，否则为 `(self, context)`。
- 可以使用 `@register("名称", "作者", "描述", "版本")` 装饰器（高版本框架已废弃，推荐在 metadata.yaml 中定义）。

### 3.2 核心装饰器一览

| 装饰器 | 用途 |
|--------|------|
| `@filter.event_message_type(EventMessageType.GROUP_MESSAGE)` | 接收群消息 |
| `@filter.event_message_type(EventMessageType.ALL)` | 接收所有消息（群+私聊） |
| `@filter.command("指令名")` | 注册指令（自动处理前缀） |
| `@filter.command("指令名", alias={"别名1", "别名2"})` | 带别名的指令 |
| `@filter.permission_type(PermissionType.ADMIN)` | 仅管理员可用 |
| `@filter.permission_type(PermissionType.ADMIN, raise_error=False)` | 权限不足时不主动报错 |
| `@filter.on_llm_request()` | LLM 请求前处理（注入提示词等） |
| `@filter.on_llm_response()` | LLM 响应后处理（过滤、修改回复） |
| `@filter.on_decorating_result()` | 消息发送前处理（修改最终输出） |
| `@filter.on_astrbot_loaded()` | 框架加载完成时执行初始化 |
| `@filter.after_message_sent()` | 消息成功发送后触发 |
| `@filter.llm_tool("工具名")` | 注册 LLM 可调用工具 |
| `@filter.platform_adapter_type(PlatformAdapterType.AIOCQHTTP)` | 限制平台（如仅 QQ/OneBot） |

所有装饰器均可传入 `priority` 参数（整型，值越大越先执行）：
```python
@filter.event_message_type(EventMessageType.GROUP_MESSAGE, priority=888)
```

### 3.3 事件处理方法

#### 指令处理（推荐，自动解析参数）

```python
@filter.command("设置")
async def set_cmd(self, event: AstrMessageEvent, key: str = "", value: str = ""):
    # 框架自动按空格分割参数：/设置 key value -> key="key", value="value"
    if not key:
        yield event.plain_result("请输入键名")
        return
    # ... 处理逻辑
    yield event.plain_result(f"已设置 {key} = {value}")

@filter.command("设置全部")
async def set_all(self, event: AstrMessageEvent):
    text = event.get_message_str().strip().split()[1]
    yield event.plain_result(f"收到的参数：{text}")
```

#### 消息类型过滤

```python
@filter.event_message_type(EventMessageType.GROUP_MESSAGE)
async def on_group(self, event: AstrMessageEvent):
    pass

@filter.event_message_type(EventMessageType.ALL)
async def on_all(self, event: AstrMessageEvent):
    pass
```

#### 平台过滤

```python
@filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
async def on_qq(self, event: AstrMessageEvent):
    pass
```

#### 组合使用

```python
@filter.event_message_type(EventMessageType.GROUP_MESSAGE)
@filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
async def on_qq_group(self, event: AiocqhttpMessageEvent):
    pass
```

#### LLM 请求/响应处理

```python
from astrbot.api.provider import ProviderRequest, LLMResponse

@filter.on_llm_request()
async def llm请求前(self, event: AstrMessageEvent, req: ProviderRequest):
    req.system_prompt += "\n额外提示词：当前群号是..." 

@filter.on_llm_response()
async def llm请求后(self, event: AstrMessageEvent, resp: LLMResponse):
    resp.completion_text = resp.completion_text.replace("敏感词", "***")
```

#### 结果装饰器（发送前篡改）

```python
from astrbot.api.all import Plain

@filter.on_decorating_result()
async def 发送消息前(self, event: AstrMessageEvent):
    result = event.get_result()
    for seg in result.chain:
        if isinstance(seg, Plain) and seg.text:
            seg.text = seg.text.replace("临时占位", "最终内容")
```

### 3.4 消息处理流程（返回值方式）

```python
# 方式一：yield 返回（推荐，可多次返回）
@filter.command("测试")
async def test(self, event: AstrMessageEvent, text: str = ""):
    if not text:
        yield event.plain_result("请输入内容")
        return
    event.stop_event()  # 阻止后续插件处理
    yield event.plain_result(f"你说的是: {text}")

# 方式二：async for 调用子方法
@filter.command("签到")
async def sign(self, event: AstrMessageEvent):
    event.stop_event()
    async for result in self._do_sign(event):
        yield result

# 方式三：直接 send（后台任务）
await event.send(event.plain_result("异步通知"))
```

---

## 四、Event API 参考

### 4.1 常用属性/方法

```python
event.get_message_str()       # 获取纯文本消息
event.message_str              # 属性形式
event.get_messages()           # 获取消息链 list[BaseMessageComponent]
event.get_group_id()           # 群号 (str)，私聊时返回空字符串
event.get_sender_id()          # 发送者 ID (str)
event.get_sender_name()        # 发送者昵称 (str)
event.get_self_id()            # 机器人自身 ID (str)
event.get_session_id()         # 会话 ID (str)
event.unified_msg_origin       # 消息来源标识 (str)
event.is_admin()               # 发送者是否为管理员 (bool)
event.is_at_or_wake_command    # 是否被 @ 或唤醒

# 事件控制
event.stop_event()             # 阻止后续插件处理同一消息
event.set_extra("key", value)  # 设置额外信息，可在请求各阶段间传递数据
event.get_extra("key")

# 回复结果构建
event.plain_result("文本")                  # 纯文本消息
event.image_result("路径/URL")              # 图片消息
event.chain_result([Plain(...), At(...)])   # 自定义消息链
```

### 4.2 消息段类型

```python
from astrbot.api.all import Plain, Image, At, Reply, Poke

# 解析接收到的消息
for seg in event.get_messages():
    if isinstance(seg, Plain):
        print(seg.text)           # 纯文本
    elif isinstance(seg, At):
        print(seg.qq, seg.name)   # 被 @ 的 QQ 号和昵称（int|str)
    elif isinstance(seg, Reply):
        print(seg.id)             # 被引用消息 ID（int|str)
        print(seg.chain)          # 被引用消息链
        print(seg.sender_id)      # 被引用消息发送者 ID（int|str)
    elif isinstance(seg, Image):
        print(seg.url)            # 图片 URL（str|None)
        print(await seg.convert_to_base64())  #图片的 base64 字符串，不以 base64:// 或者 data:image/jpeg;base64, 开头。

# 构建消息段
async def 构造并发送消息链(event: AstrMessageEvent, 文本: str = None, 回复: bool = False, 艾特: bool = False,
            base图片: str = None, URL图片: str = None, 本地图片:str=None):
    消息链 = []
    if 回复:
        消息链.append(Reply(id=event.message_obj.message_id))
    if 艾特:
        消息链.append(At(qq=event.get_sender_id()))
    if 文本:
        消息链.append(Plain(text=文本))
    if base图片:
        消息链.append(Image.fromBase64(base图片))
    if URL图片:
        消息链.append(Image.fromURL(URL图片))
    if 本地图片:
        消息链.append(Image.fromFileSystem(本地图片))
    await event.send(event.chain_result(消息链))
    return
```
**注意**：在构造消息链时，如需Reply组件，必须放在第一位

### 4.3 OneBot 平台专属 API（aiocqhttp）

```python
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

# 需确保 event 为 AiocqhttpMessageEvent 类型
await event.bot.get_group_member_info(group_id=int(群号), user_id=int(QQ号))
await event.bot.get_group_member_list(group_id=int(群号))
await event.bot.set_group_ban(group_id=int(群号), user_id=int(QQ号), duration=秒数)
await event.bot.delete_msg(message_id=int(消息ID))
await event.bot.call_action("send_group_msg", group_id=int(群号), message=消息)
await event.bot.call_action("send_private_msg", user_id=int(QQ号), message=消息)
```

**注意**：群号和 QQ 号在存储时为 `str`，调用 API 时需转为 `int`。

---

## 五、配置系统 (_conf_schema.json)

### 5.1 基本结构

```json
{
  "配置键名": {
    "description": "显示名称",
    "type": "类型",
    "default": 默认值,
    "hint": "提示信息（可选）"
  }
}
```

支持的 `type`：`"string"`, `"int"`, `"float"`, `"bool"`, `"text"`（多行文本）, `"list"`（内容类型为 `str`）, `"object"`（需 `"items": {...}`）, `"template_list"`（需 `"templates": {...}`）。

### 5.2 特殊配置项

```json
{
  "模型选择": {
    "type": "string",
    "_special": "select_provider",
    "default": ""
  },
  "选项": {
    "type": "string",
    "options": ["选项A", "选项B", "选项C"],
    "default": "选项A"
  },
  "数量": {
    "type": "int",
    "slider": {"min": 1, "max": 100, "step": 1},
    "default": 10
  }
}
```

### 5.3 在插件中读写配置

```python
# 读取（带默认值）
self.value = config.get("key", default)

# 修改并保存
config['key'] = new_value
self.config.save_config()

# 获取框架全局配置
wake_prefix = context.get_config()["wake_prefix"]
admins = context.get_config()["admins_id"]
```

---

## 六、LLM 集成

### 6.1 直接调用 LLM

```python
chat_provider_id = await self.context.get_current_chat_provider_id(event.get_session_id())
# 或获取消息源默认模型
# provider = self.context.get_using_provider(event.unified_msg_origin)

resp = await self.context.llm_generate(
    chat_provider_id=chat_provider_id,
    prompt="用户问题",
    system_prompt="系统指令",
    contexts=history_list,         # 历史对话，格式 [{"role":"user","content":"..."}, ...]
)
reply = resp.completion_text.strip()
```

### 6.2 注册 LLM 工具（让 AI 调用）

```python
@filter.llm_tool(name="get_weather")
async def get_weather(self, event: AstrMessageEvent, city: str):
    """
    查询指定城市的天气情况
    Args:
        city(string): 城市名称
    """
    # 实际获取天气数据
    result = f"{city}的天气：晴，25°C"
    return result  # 返回的字符串会交给 LLM 整合回复
```

---


## 七、数据持久化

### 7.1 JSON 文件

```python
import json, os

data_path = os.path.join(StarTools.get_data_dir(), "data.json")

def load(self):
    if os.path.exists(self.data_path):
        with open(self.data_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

def save(self):
    with open(self.data_path, 'w', encoding='utf-8') as f:
        json.dump(self.data, f, ensure_ascii=False, indent=2)
```

### 7.2 SQLite 数据库（推荐大量数据）

```python
import sqlite3
from contextlib import closing

db_path = os.path.join(StarTools.get_data_dir(), "data.db")

# 写操作
with closing(sqlite3.connect(db_path)) as conn:
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT)')
    c.execute('INSERT OR REPLACE INTO users VALUES (?, ?)', (user_id, name))
    conn.commit()

# 读操作
with closing(sqlite3.connect(db_path)) as conn:
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id=?', (user_id,))
    row = c.fetchone()
```

### 7.3 数据目录获取

```python
from astrbot.api.star import StarTools

data_dir = StarTools.get_data_dir()   # 插件专属数据目录，返回Path对象
font_path = StarTools.get_font_path() # 系统提供的字体路径
```

---

## 八、图片处理

```python
from PIL import Image, ImageDraw, ImageFont
import io

# 打开现有图片
img = Image.open("path.png")
# 创建新画布
bg = Image.new('RGBA', (800, 600), (255, 255, 255, 255))

# 绘图
draw = ImageDraw.Draw(bg)
font = ImageFont.truetype("font.ttf", 40)
draw.text((x, y), "文本", font=font, fill=(0, 0, 0))

# 圆形裁剪
mask = Image.new('L', size, 0)
ImageDraw.Draw(mask).ellipse([0, 0, w, h], fill=255)
avatar = Image.new('RGBA', size, (0,0,0,0))
avatar.paste(img, mask=mask)

# 输出为字节流并发送
img_bytes = io.BytesIO()
bg.save(img_bytes, format='PNG')
yield event.chain_result([Image.fromBytes(img_bytes.getvalue())])

# 或临时文件方式
temp_path = "/tmp/out.png"
bg.save(temp_path)
yield event.image_result(temp_path)
os.remove(temp_path)
```

---

## 九、网络请求

```python
import aiohttp

async with aiohttp.ClientSession() as session:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        data = await resp.read()     # 二进制
        json_data = await resp.json() # JSON
        text = await resp.text()     # 文本
```

也可使用 `httpx` 库。

---

## 十、常见模式与技巧

### 10.1 获取 @ 或引用的目标用户

```python
def get_target_user(event) -> tuple:
    """返回 (用户ID, 用户名)，没有则返回 None"""
    for seg in event.get_messages():
        if isinstance(seg, At) and str(seg.qq) != event.get_self_id():
            return str(seg.qq), seg.name or ""
        if isinstance(seg, Reply):
            return str(seg.sender_id), ""
    return None
```

### 10.2 权限检查

```python
# 检查是否群主/管理员
def is_admin_or_owner(event, group_id, user_id) -> bool:
    try:
        return event.message_obj.raw_message['sender']['role'] in ('owner', 'admin')
    except Exception as e:
        logger.warning(str(e), exc_info=True)
        return False

# AstrBot 框架的管理员判断
if event.is_admin():
    pass
```

### 10.3 群组隔离数据存储

```python
self.data = {}  # { group_id: { user_id: { ... } } }

def get_user_data(self, group_id, user_id):
    if group_id not in self.data:
        self.data[group_id] = {}
    if user_id not in self.data[group_id]:
        self.data[group_id][user_id] = default_value
    return self.data[group_id][user_id]
```

### 10.4 异步后台任务

```python
self._tasks = set()

async def some_bg_work(self):
    # 耗时操作
    pass

task = asyncio.create_task(self.some_bg_work())
task.add_done_callback(self._tasks.discard)
self._tasks.add(task)

# 在 terminate 中清理
async def terminate(self):
    for task in self._tasks:
        if not task.done():
            task.cancel()
    if self._tasks:
        await asyncio.gather(*self._tasks, return_exceptions=True)
```

### 10.5 异步锁

```python
import asyncio

self.lock = asyncio.Lock()
async with self.lock:
    # 临界区操作
    pass
```

---

## 十一、常用导入一览

```python
# 核心
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.all import Star, Context, AstrBotConfig, logger
from astrbot.api.all import Plain, Image, At, Reply, Poke, Json, MessageChain

# 平台适配
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

# LLM 相关
from astrbot.api.provider import ProviderRequest, LLMResponse

# 工具
from astrbot.api.star import register, StarTools
```

---

## 十二、避坑指南

1. **ID 类型**：群号、用户 ID 在框架中以 `str` 存储，传给 OneBot API 时转 `int`。
2. **配置持久化**：修改 `config` 后可调用 `self.config.save_config()`保存配置。
3. **私聊群号**：`event.get_group_id()` 在私聊时返回空字符串。
4. **图片来源**：生成图片后记得清理临时文件；也可使用 `BytesIO` 避免文件残留。
5. **异步 IO**：在异步方法中避免使用同步阻塞 IO（如 `requests`），使用 `aiohttp` 或 `httpx`。
6. **priority 顺序**：值越大越先执行。
7. **热加载**：修改 `_conf_schema.json` 后需要重载插件才能生效。