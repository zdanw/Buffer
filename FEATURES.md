# Buffer社交内容发布系统 - 功能清单

## 一、系统概述

基于Flask框架构建的**社交媒体内容自动化发布系统**，集成Chroma向量知识库、Doubao-Seedream-4.5 AI和Buffer API。

---

## 二、功能模块清单

### 1. 图文知识库模块

| 功能点 | 说明 | 实现位置 |
|--------|------|----------|
| 语义搜索 | 基于Chroma向量数据库的关键词搜索，支持相似度阈值过滤 | `app/services/chroma_service.py` |
| 搜索建议 | 根据关键词获取相关搜索建议词 | `app/services/chroma_service.py` |
| 字段搜索 | 按指定字段（产品名称、文案内容等）搜索 | `app/services/chroma_service.py` |
| 标签搜索 | 根据标签获取相关条目 | `app/services/chroma_service.py` |
| 条目管理 | 新增、编辑、删除知识库条目 | `app/api/knowledge.py` |
| 图片上传 | 支持本地图片上传到GitHub图床 | `app/api/knowledge.py` |
| 同义词扩展 | 搜索时自动扩展同义词 | `app/services/chroma_service.py` |
| 搜索缓存 | 自动缓存搜索结果，提升响应速度 | `app/services/chroma_service.py` |

---

### 2. AI内容生成模块

| 功能点 | 说明 | 实现位置 |
|--------|------|----------|
| 文案生成 | 使用DeepSeek模型生成社交媒体种草文案 | `app/services/ai_service.py` |
| 图片生成 | 使用Doubao-Seedream-4.5模型生成产品图片 | `app/services/ai_service.py` |
| 文案去重 | 生成文案时检测与已有内容的相似度，确保唯一性 | `app/services/ai_service.py` |
| 图片去重 | 使用CLIP模型检测图片视觉相似度 | `app/services/ai_service.py` |
| 多风格文案 | 支持多种写作风格：幽默搞笑、温情治愈、专业测评、故事叙述、实用干货 | `app/services/ai_service.py` |
| 参考图片引导 | 生成图片时支持参考图片和Logo引导，保持品牌一致性 | `app/services/ai_service.py` |

---

### 3. 多平台发布模块

| 功能点 | 说明 | 实现位置 |
|--------|------|----------|
| Buffer集成 | 通过Buffer API连接社交媒体账号 | `app/services/buffer_service.py` |
| 多平台支持 | 支持TikTok、Instagram、Facebook发布 | `app/services/buffer_service.py` |
| 批量发布 | 一键发布到多个平台 | `app/services/buffer_service.py` |
| 立即发布 | 即时发布到社交平台 | `app/services/buffer_service.py` |
| 定时发布 | 支持设置定时发布时间（ISO格式） | `app/services/buffer_service.py` |
| 频道管理 | 获取Buffer账户的频道列表，支持缓存 | `app/services/buffer_service.py` |
| TikTok图片调整 | 自动调整图片尺寸以满足TikTok像素限制 | `app/services/buffer_service.py` |

---

### 4. 发布模式模块

| 功能点 | 说明 | 实现位置 |
|--------|------|----------|
| 全自动模式 | 一键完成：搜索→生成文案→生成图片→发布→保存到知识库 | `app/api/publish.py` |
| 半自动模式 | 先生成内容，预览确认后再发布，支持单独重新生成文案或图片 | `app/api/publish.py` |
| 重新生成 | 支持单独重新生成文案、图片，或同时重新生成 | `app/api/publish.py` |
| 直接发布 | 使用知识库已有内容直接发布 | `app/api/publish.py` |

---

### 5. 产品管理模块

| 功能点 | 说明 | 实现位置 |
|--------|------|----------|
| 产品列表 | 维护产品名称和描述信息 | `app/api/products.py` |
| 新增产品 | 添加新产品到列表 | `app/api/products.py` |
| 编辑产品 | 修改产品名称和描述 | `app/api/products.py` |
| 删除产品 | 删除产品及相关知识库条目 | `app/api/products.py` |

---

### 6. GitHub图床模块

| 功能点 | 说明 | 实现位置 |
|--------|------|----------|
| 图片上传 | 将图片上传到GitHub仓库 | `app/services/github_service.py` |
| URL转换 | 将GitHub blob链接转换为jsDelivr CDN链接 | `app/services/github_service.py` |
| 上传历史 | 记录最近的上传记录 | `app/services/github_service.py` |
| 配置检查 | 验证GitHub图床配置是否完整 | `app/services/github_service.py` |

---

### 7. 系统工具模块

| 功能点 | 说明 | 实现位置 |
|--------|------|----------|
| 配置信息 | 获取系统配置、产品列表、支持的平台 | `app/api/utils.py` |
| URL批量转换 | 批量转换知识库中的GitHub URL为CDN地址 | `app/api/utils.py` |
| 结构化日志 | 支持控制台彩色输出和JSON文件输出 | `app/services/logger.py` |
| 多环境配置 | 支持开发、生产、测试三种环境配置 | `app/config.py` |

---

## 三、技术特性

| 特性 | 说明 |
|------|------|
| **应用工厂模式** | `app/__init__.py`中的`create_app()`支持多环境配置切换 |
| **服务层分离** | `services/`目录包含纯Python业务逻辑，无Flask依赖 |
| **API模块化** | 使用Flask Blueprint统一管理API路由 |
| **向量数据库** | 基于Chroma实现语义搜索和相似度计算 |
| **缓存机制** | 搜索缓存、条目缓存、嵌入向量缓存 |
| **错误重试** | API调用支持指数退避重试机制 |
| **日志系统** | 支持控制台彩色输出和JSON文件日志 |

---

## 四、支持的社交平台

| 平台 | ID | 图标 | 特殊处理 |
|------|----|------|----------|
| TikTok | `tiktok` | 🎵 | 自动调整图片尺寸（1080x1080限制） |
| Instagram | `instagram` | 📷 | 需要图片URL |
| Facebook | `facebook` | 📘 | 支持纯文本和图片 |
| Twitter/X | `twitter` | 🐦 | 支持纯文本 |
| LinkedIn | `linkedin` | 💼 | 支持纯文本 |
| Pinterest | `pinterest` | 📌 | 需要图片URL |
| YouTube | `youtube` | 📺 | 支持视频链接 |
| Threads | `threads` | 🧵 | 支持图片 |
| Mastodon | `mastodon` | 🐘 | 支持纯文本 |

---

## 五、核心API接口汇总

| 模块 | 接口 | 方法 | 说明 |
|------|------|------|------|
| 基础 | `/api/config/info` | GET | 获取系统配置 |
| 知识库 | `/api/search` | GET | 语义搜索 |
| 知识库 | `/api/entries` | POST/GET | 新增/获取条目 |
| 知识库 | `/api/entries/<id>` | PUT/DELETE | 更新/删除条目 |
| 内容生成 | `/api/generate` | POST | 生成内容（文案+图片） |
| 内容生成 | `/api/regenerate` | POST | 重新生成内容 |
| 发布 | `/api/publish` | POST | 发布到社交平台 |
| 发布 | `/api/auto_publish` | POST | 全自动发布 |
| 产品 | `/api/products` | GET/POST | 获取/添加产品 |
| 产品 | `/api/products/<index>` | PUT/DELETE | 更新/删除产品 |

---

## 六、文件结构

```
c:\IDE_pro_Buffer/
├── app/
│   ├── __init__.py          # Flask应用工厂
│   ├── config.py            # 配置管理（多环境支持）
│   ├── api/                 # API路由层
│   │   ├── __init__.py
│   │   ├── knowledge.py     # 知识库API
│   │   ├── publish.py       # 内容生成与发布API
│   │   ├── products.py      # 产品管理API
│   │   └── utils.py         # 工具API
│   ├── services/            # 业务服务层
│   │   ├── chroma_service.py    # Chroma向量知识库操作
│   │   ├── buffer_service.py    # Buffer平台API集成
│   │   ├── ai_service.py        # AI内容/图像生成
│   │   ├── github_service.py    # GitHub图床服务
│   │   └── logger.py            # 日志模块
│   ├── static/              # 静态文件
│   └── templates/           # HTML模板
├── data/                    # 数据目录
│   ├── chroma_db/           # Chroma向量数据库
│   ├── uploads/             # 上传图片存储
│   ├── logs/                # 日志文件
│   └── products.json        # 产品列表配置
├── run.py                   # 开发环境启动脚本
├── wsgi.py                  # 生产环境WSGI入口
├── requirements.txt         # Python依赖列表
└── FEATURES.md              # 功能清单（本文件）
```

---

**生成时间**: 2026-06-02
**版本**: v2.1.0