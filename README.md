# AstrBot Phi Plugin Query Core

AstrBot 原生 Phigros 查询核心插件，基于 `phi-plugin` 的资源与算法分阶段重构。

## 当前支持

- `phi help`：查看帮助与迁移状态
- `phi song <曲名或别名>`：查询曲目信息
- `phi search <关键词>`：搜索曲目
- `phi rand`：随机曲目
- `phi ill <曲名或别名>`：发送本地曲绘（存在时）
- `phi bind <sessionToken>`：绑定 token
- `phi unbind`：解绑并清理缓存
- `phi clean`：清理当前用户插件数据
- `phi update`：尝试从查询 API 拉取并缓存标准化存档
- `phi b30` / `phi rks`：基于缓存存档输出 B30/RKS 摘要
- `phi score <曲名或别名>`：查询单曲成绩
- `phi info`：查询用户统计摘要

命令触发使用 AstrBot 原生 `@filter.command("phi")`，实际前缀由 AstrBot 全局唤醒/命令配置处理，本插件不再自行监听 `#` 或 `/`。

## 迁移说明

第一阶段不依赖 Node.js、Yunzai、Redis 或 Puppeteer。图片模板、小游戏、排行榜、评论、标签、签到任务、管理命令和插件自更新暂未迁移。

运行期数据、绑定、缓存和后续下载数据均写入 `StarTools.get_data_dir("astrbot_plugin_phi_plugin")` 对应的 AstrBot 插件数据目录；插件包内 `resources/` 只存放随插件发布的静态曲库资源。

如果 `phi update` 所连接的服务没有返回标准化存档 JSON，插件会给出安全提示；后续可以在 `phi_core/save/client.py` 与 `phi_core/save/codec.py` 中继续补齐云存档协议。
