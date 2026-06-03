# AstrBot Phi Plugin

AstrBot 原生 Phigros 查询插件，基于 [Catrong/phi-plugin](https://github.com/Catrong/phi-plugin) 的曲库资源、算法思路和 HTML 模板进行迁移。当前版本使用 AstrBot 命令组、插件数据目录、配置面板和 HTML/T2I 渲染接口，不依赖 Yunzai、Redis、Node.js 或自建 Puppeteer。

## 功能概览

| 类别 | 功能 |
|---|---|
| 查分 | `pgr`、`phi pgr`、`phi b30/bN`、`phi rks`、`phi p30/pN`、`phi x30/xN`、`phi fc30/fcN`、`phi best`、`phi score`。 |
| 玩家信息 | `phi update`、`phi info/info1/info2`、`phi data`、`phi hisb30`、`phi 2025history`、`phi achievement/ahv`。 |
| 曲库 | `phi song`、`phi chart`、`phi ill`、`phi search`、`phi alias`、`phi table`、`phi chap`、`phi rand`、`phi randclg`。 |
| 在线功能 | `phi ranklist`、`phi rankfind`、`phi comment/cmt`、`phi tag`、`phi settag`、`phi addtag`、`phi newlog`、`phi newnotice`、`phi live`。 |
| 绑定登录 | `phi bind`、`phi cnbind`、`phi gbbind`、`phi auth/login`、`phi unbind`、`phi clean`、`phi id`、`phi sessiontoken/tk/token`。 |
| 小游戏 | `phi guess`、`phi tipgame`、`phi ltr/letter`、`phi tip`、`phi ans`、`phi open`。 |
| Notes/设置 | `phi sign`、`phi task`、`phi retask`、`phi send`、`phi jrrp`、`phi theme`、`phi myset`。 |
| 资源维护 | `phi down resources`、`phi down ill`、`phi down all`、`phi renderdiag`。 |

## 运行特点

- 命令使用 AstrBot 原生 `phi` 命令组注册，不再保留插件内部 `#` 和 `/` 触发词。
- 运行期数据写入 AstrBot 插件数据目录，不写入源码目录。
- 首次安装缺少资源时会自动拉取 Jinja2 模板、`info` 曲库和 `otherill` 资源。
- 可配置定时自动更新模板、曲库信息和 `otherill`，不会自动下载完整曲绘仓库。
- 默认使用远程曲绘模式，把 GitHub 曲绘 URL 传给 T2I；也可切换成本地曲绘 base64 模式。
- 图片发送先尝试原图，失败后依次尝试 JPG、WebP，全部失败时发送文本提示。
- `phi guess`、`phi tipgame`、`phi ltr` 可选择开启普通消息监听，也保留命令唤醒方式。

## 资源来源

| 资源 | 来源 | 保存位置 |
|---|---|---|
| Jinja2 HTML 模板 | `kyuphoenix/astrbot_plugin_phi_plugin_jinja2_template` | `downloads/html` |
| 原版 `info` 和 `otherill` | `Catrong/phi-plugin` 的 `resources` | `downloads/info`、`downloads/otherill` |
| 曲绘 | `Catrong/phi-plugin-ill` | `downloads/original_ill` |

`github_proxy` 用于资源仓库下载和远程曲绘下载加速。`illustration_url_proxy` 只用于传给 T2I 的远程曲绘 URL。

## 开发文档

当前插件的详细逻辑链路、扩展命令流程、渲染链路和调试方式请看：[`docs/developer-guide.md`](docs/developer-guide.md)。

## 常用验证

```powershell
$env:PYTHONIOENCODING='utf-8'
python -m py_compile main.py phi_core\config.py phi_core\commands\__init__.py phi_core\commands\_rendering.py phi_core\render\jinja_renderer.py phi_core\render\jinja_adapter.py phi_core\render\panel.py
python scripts\smoke_command_group.py
python scripts\smoke_command_routes.py
python scripts\smoke_command_locks.py
python scripts\smoke_game_reply_listener.py
python scripts\smoke_resource_download.py
python scripts\smoke_jinja_render_chain.py
python scripts\smoke_dispatch.py
python scripts\smoke_image_send_variants.py
python scripts\smoke_image_send_fallback_flow.py
```
