# 取消 HTML / 附件本地化存储

## 背景

当前爬虫链路把每页的**原始 HTML**、**清理后 HTML**、**图片/CSS/JS/字体等静态资源**全部物化到 PostgreSQL 和本地 `crawl-cache/`。分析后确认这些产物在 RAG 链路中**完全不被使用**——embedding/检索只读 `documents.content`（Markdown 切片）。前端 DocReader 的 HTML tab（iframe + `/preview` 路由 + `documents.clean_html` + 注入 `<base>` 指向本地 `/static` 资源）是 HTML/附件物化数据的唯一消费者。

经过多轮 review，**决定下线 HTML tab**：
- iframe 嵌入被大面积拒绝（Apple/GitHub/Stack Overflow/Cloudflare/Notion/Medium/微信文章/Confluence 等）
- 即便嵌入成功，原页面是"现在时"，与 RAG 引用的"抓取时"内容漂移，对照无价值
- "想看原网页"的需求用顶部一个外链按钮即可覆盖，一次点击直达

代价：磁盘 72 MB 缓存（4 个域名，主大头在 `assets/`）、`task_service._rewrite_html_links` / `_mirror_asset` / `document_service._inject_base_tag` 一整条复杂链路、`extract_links_from_html` 强依赖 `html_content` 做断点续传。

目标：取消所有附件本地化（`_mirror_asset` / `_rewrite_*` / `<base>` 注入 / `/static` 路由全删）；前端去掉 HTML tab，只展示 Markdown（默认内容）+ 顶部"打开原网页"外链按钮；`clean_html` / `html_content` 字段都不再写入（drop 列）；断点续传改为爬虫阶段直接落 manifest；前后端 Document 类型/DTO/响应字段同步。

## 设计决策

1. **DocReader 简化为单一 Markdown 视图** —— 去掉 HTML tab 与 iframe；顶部"原文"小图标链接强化为明显按钮"打开原网页"（带外链图标，`target="_blank" rel="noopener noreferrer"`），承担"想看原网页"的真实需求；当 `doc.url` 缺失时按钮 `disabled` + `title="无原始链接"` tooltip
2. **`html_content` / `clean_html` 字段废弃 + 迁移删除** —— DocReader 不再读 DB 的 HTML，前后端 Document 类型/DTO/响应字段同步
3. **断点续传**：爬虫阶段把每页抽出的链接列表（`SimpleCrawlResult.links` 已存在）增量写入 `crawl-cache/<domain>/manifests/links.json`，中断后从 manifest 恢复 BFS 队列
4. **manifest 增长管理**：抓取阶段收尾时做一次 `merge & dedup`（同 domain 内 values 去重）
5. **manifest 启动恢复清理**：跨域链接按当前 `domain_key` 过滤、同链接 set 去重、应用 `prefixes` 与 `skip_urls` 过滤

## 实施步骤

### 1. 数据库迁移（后端）

新文件 `backend/migrations/versions/` 下新增 alembic 迁移：
- `upgrade()`：`op.drop_column("documents", "html_content")`、`op.drop_column("documents", "clean_html")`
- `downgrade()`：`op.add_column("documents", "html_content", Text, nullable=True)` 与 `clean_html` 同理
- 保留 `source_path` 字段（仍可作元数据）

文件变更：
- `backend/database/models/document.py` —— 删除 `html_content` 和 `clean_html` 两个 `Mapped[Optional[str]]` 定义
- `backend/services/task_service.py` —— `crawled_docs` 过滤条件去掉 `d.clean_html` 改为 `d.uri and d.source_path`
- `backend/database/repositories/*.py` —— 移除构造 DTO 时传递 `html_content` / `clean_html` 的相关代码
- `backend/models/dto.py` —— DocumentDTO 移除对应字段
- API 响应序列化层（`backend/api/routes/collections.py` 等）—— grep 兜底确认无残留引用

### 2. 爬虫改造

**确认 Scrapy 路径**：
- 阅读 `backend/crawler/scrapy_document_spider.py` 与 `scrapy_web_crawler.py`
- 如果 Scrapy 也走 `TaskService._process_single_page` / `_store_crawled_page` → 当前 plan 充分
- 如果不走 → 需补 Scrapy 路径独立的清理点（参考 TaskService 改造方法）

**SimpleCrawler 简化**（`backend/crawler/simple_web_crawler.py`）：
- `SimpleCrawlResult.html_content` 和 `clean_html` 字段删除（调用方不再需要）
- `extract_links_from_html` 静态方法删除（断点续传改走 manifest）
- `_clean_html` 私有方法删除（无人调用）
- 保留 `_extract_content` 返回 `links: list[str]`

### 3. TaskService 清理

**删除**（`backend/services/task_service.py`）：
- 整个 `rewrite_static` 阶段 —— 从 `STAGES` 列表移除
- `_rewrite_html_links` 方法
- `_mirror_asset` 方法
- `_rewrite_css_references` / `_rewrite_srcset` / `_should_skip_reference` / `_relative_link` / `_domain_key` / `_canonicalize_page_url` / `_source_path_to_page_rel_path` / `_render_markdown_frontmatter` 等私有 helper
- `_delete_crawl_cache` 调整：保留 `manifests/`，清掉 `pages/` 与 `assets/`
- 提取 `extract_links_from_html` 调用（断点续传改用 manifest 恢复）

**断点续传改造**：
- 删除依赖 `doc.html_content` 调 `extract_links_from_html` 的恢复逻辑
- 改为：读 `<cache_root>/<domain>/manifests/links.json`（按域名），恢复种子队列
- manifest 落盘位置：`config.get_crawl_cache_dir() / <domain_key> / manifests / links.json`
- manifest 格式：`{"<canonical_page_url>": ["<link1>", "<link2>", ...], ...}`（key=已抓取的页 URL，value=其出链）
- manifest 写入时机：在 `_process_single_page` 落库成功后，把 `crawl_result.links` 增量写入对应 `<domain>/manifests/links.json`

**manifest 启动恢复清理**：
- 启动恢复时按当前任务 `url_configs` 的 `seed_urls` 域名，确定要加载的 `domain_key`
- 对应 manifest 加载后：
  - 用 set 去重所有 values（同一链接可能被多个 page 引用）
  - 按 `domain_key` 过滤跨域链接（虽然 `_extract_content` 已过滤同域，启动时再保险一次）
  - 应用 `prefixes` 过滤（限缩的 prefix 不再匹配时跳过）
  - 应用 `skip_urls` 过滤（已 indexed 的不再爬）

**manifest 抓取完成收尾**：
- 任务 `crawl` 阶段完成后，做一次 `merge & dedup`：
  - 同 domain 的 values 用 set 去重
  - 不强制重写文件，依赖读时合并
- 不在 migration 时清空 manifest（保留供断点续传）

**新文件** `backend/crawler/manifest_store.py`：
- 集中处理 manifest 读/写/增量合并
- 并发安全：`threading.Lock`（同进程内 ThreadPoolExecutor 5 线程够用）
- 写入用临时文件 + 原子重命名（`Path.replace()`）
- 多进程并发备注：当前同进程方案够用，未来多 uvicorn worker 需 `portalocker` 升级 —— 不强制实施

### 4. 文档服务清理

`backend/services/document_service.py`：
- 整段 `_compute_preview_base_href` / `_inject_base_tag` / `preview_document` —— 删除
- 移除导入的 `Response`、`re`（如不再用）、`Path` 等

`backend/api/routes/documents.py`：
- `GET /api/v1/collections/{cid}/documents/{did}/preview` 路由删除（前端不再调用）

`backend/api/routes/collections.py`：
- `GET /api/v1/collections/{cid}/static/{path:path}` 路由删除（不再提供本地化资源）

### 5. 前端

`frontend/src/components/knowledge/DocReader.tsx` 整体简化：

- **去掉顶部 tab 切换 UI**：`viewMode` state、`ViewMode` type、`setViewMode` 全部移除
- **去掉 iframe 块**：iframe 元素、`previewUrl` 引用、HTML 加载相关 state/effect 全部删除
- **去掉 `savedScrollTop` 死代码**：ref + 监听 `viewMode` 的 useEffect/useLayoutEffect 移除
- **简化 Markdown 加载**：`loadMarkdown` 触发改为 `useEffect(on mount + doc.id change)`，不再依赖 `viewMode`
- **强化顶部"打开原网页"按钮**：把现有"原文"小图标链接改成更明显的主按钮（`border border-accent/30 bg-accent/5 hover:bg-accent/10 text-accent rounded-lg px-3 py-1.5` 等符合 Apple Liquid Glass 风格的样式），`target="_blank" rel="noopener noreferrer"` 保留
- **当 `doc.url` 缺失时**：按钮 `disabled` + `title="无原始链接"` tooltip
- **`DocReaderProps` 移除 `previewUrl: string`**
- **保留 Markdown 渲染逻辑**：加载 + `markdownToHtml` + 渲染 —— 这是 doc 详情页的**唯一内容**
- **保留 `handleClick` 锚链接/外链处理**：Markdown 内的链接交互仍需
- **清理不再用的 import**：`CodeBracketIcon`、`DocumentTextIcon`（如不再用）等

`frontend/src/components/knowledge/KnowledgeBaseManagement.tsx`：
- 移除 `previewUrl` prop 传递

`frontend/src/services/apiClient.ts`：
- `getDocumentPreviewUrl` 函数删除
- 同步更新 `Document` TypeScript 类型（移除 `html_content` / `clean_html` 字段如存在）
- grep `html_content` / `clean_html` 兜底所有调用方

`frontend/src/**/*.test.tsx`：
- 移除 DocReader HTML 模式用例
- 保留 Markdown 渲染用例
- 补 Markdown 加载时机调整的用例（on mount 触发，不依赖 viewMode）
- 补 `doc.url` 缺失时按钮 disabled 的用例
- 补强化版"打开原网页"按钮的可访问性/键盘导航用例

### 6. 一次性数据迁移（用户已有数据）

`~/.ai-document-assistant/crawl-cache/` 当前 72 MB：
- `pages/`、`assets/` 目录：可直接删除（preview 已下线，无人读）
- `manifests/links.json`：若不存在，新逻辑会重建；旧的 `pages.json` / `assets.json` / `failed_assets.json` 可一并删除

在迁移发布时附带一段说明（README 段落或迁移脚本），告知用户旧缓存可清理。**不在迁移脚本里自动 `rm -rf`**，避免误删——提供可选脚本 `backend/scripts/clean_legacy_crawl_cache.py` 列出将要删除的内容让用户确认。

### 7. 测试更新

后端（pytest）：
- 移除 `tests/` 中对 `html_content` / `clean_html` 字段写入与读取的断言
- 新增 `test_manifest_store.py`：覆盖
  - `links.json` 的并发增量写入
  - 读时跳过已处理 URL
  - 启动恢复时的去重 + 跨域过滤 + prefix/skip_urls 过滤
  - 抓取完成时的 `merge & dedup`
- 更新 `test_task_service.py`：`rewrite_static` 阶段被移除后，对应测试改测 manifest 落盘
- 更新 `test_document_service.py`：移除 `preview_document` / `_inject_base_tag` 相关用例
- 补 Scrapy 路径的测试（如 Scrapy 也走 TaskService 跳过；否则单独补）

前端（vitest）：
- 移除 `DocReader.test.tsx` 中 HTML 模式用例
- 保留 Markdown 渲染用例
- 补 Markdown 加载时机调整用例
- 补 `doc.url` 缺失时按钮 disabled 用例
- 补"打开原网页"按钮的可访问性/键盘导航用例

## 关键复用点

- **`SimpleCrawlResult.links`**（`backend/crawler/simple_web_crawler.py`）—— 已是结构化数据，直接喂给 manifest
- **`_clean_url` 规范化**（`backend/crawler/simple_web_crawler.py`）—— manifest 写入时复用保证 key 一致
- **`config.get_crawl_cache_dir()`**（`backend/models/config.py`）—— manifest 路径计算
- **`skip_urls` 现有 dedup 机制**（`backend/services/task_service.py`）—— manifest 恢复后过滤

## 涉及文件

后端（修改/删除）：
- `backend/database/models/document.py` — 删字段
- `backend/models/dto.py` — 删字段
- `backend/services/task_service.py` — 删阶段、删方法、改断点续传
- `backend/services/document_service.py` — 删 preview 系列
- `backend/api/routes/documents.py` — 删 preview 路由
- `backend/api/routes/collections.py` — 删 static 路由
- `backend/crawler/simple_web_crawler.py` — 删 `SimpleCrawlResult` 中 HTML 字段、删 `extract_links_from_html`、删 `_clean_html`
- `backend/crawler/scrapy_document_spider.py` — 确认/补清理（如 Scrapy 路径不走 TaskService）
- `backend/crawler/scrapy_web_crawler.py` — 确认/补清理
- `backend/database/repositories/*.py` — 删字段传递
- `tests/**/*.py` — 更新/删除

后端（新增）：
- `backend/crawler/manifest_store.py` — manifest 读写 + 启动恢复清理 + 收尾 dedup
- `backend/migrations/versions/<hash>_drop_html_columns.py` — alembic 迁移
- `backend/scripts/clean_legacy_crawl_cache.py` — 旧缓存清理脚本

前端：
- `frontend/src/components/knowledge/DocReader.tsx`
- `frontend/src/components/knowledge/KnowledgeBaseManagement.tsx`
- `frontend/src/services/apiClient.ts`（含 `Document` 类型同步）
- `frontend/src/**/*.test.tsx` 相关

## 验证

1. **迁移可逆性**：先 `alembic upgrade head` 应用迁移，`alembic downgrade -1` 能回退
2. **端到端 URL 抓取**：新抓一个域名 → `documents` 表无 `html_content` / `clean_html` 列；Markdown 切片正常入 Chroma；RAG 问答返回正确引用
3. **断点续传**：
   - 抓取中点取消 → 重新启动同 collection → manifest 中的链接被消费
   - prefix 过滤生效（已不匹配的 prefix 链接不重抓）
   - 不重复抓取已 `indexed` 的 URL
4. **manifest 启动恢复清理**：跨域链接被过滤、重复链接 set 去重、prefix/skip_urls 过滤生效
5. **manifest 收尾**：抓取完成后 manifest values set 去重
6. **前端**：
   - DocReader 无 tab 切换，**只有 Markdown 内容** + 顶部"打开原网页"按钮
   - 当 `doc.url` 缺失时按钮 disabled + tooltip
   - `/preview` 接口已下线（路由不存在 → 404）
   - Markdown 加载在 mount + doc.id 变化时触发（不再依赖 viewMode）
7. **API 同步**：后端响应无 `html_content` / `clean_html` 字段；前端 TypeScript 类型同步；前端无引用编译错误
8. **Scrapy 路径**（如适用）：Scrapy 抓取完成后 manifest 落盘正常、DocReader 渲染无异常
9. **磁盘**：抓取完成后 `<cache_root>/<domain>/` 下只剩 `manifests/`，无 `pages/`、`assets/`
10. **回归**：现有所有 pytest + vitest 通过
11. **API smoke**：`curl -i http://localhost:8000/api/v1/collections/{cid}/documents/{did}/preview` → 404

## 风险与回退

- 风险 1：用户失去"在主应用内看原网页"的能力，必须跳出到浏览器新窗口
- 风险 2：原 URL 失效（404、改版、需登录）时，"打开原网页"按钮点击后看到的是错误页/登录页 —— 之前 iframe 也是同样结果
- 风险 3：内网抓取的文档，原始 URL 在云端前端不可达 —— "打开原网页"按钮无意义（但 Markdown 内容仍能看，符合 RAG 工作流）
- 风险 4：manifest 长期累积导致磁盘增长 —— 抓取完成时 `merge & dedup` 缓解
- 风险 5：多 uvicorn worker 时 manifest 写入有竞态 —— 当前同进程方案够用，备注未来用 `portalocker` 升级
- 回退：迁移脚本 `alembic downgrade -1` 即可恢复 `html_content` / `clean_html` 列；前端 `git revert` 切回 DocReader 双 tab 即可
- 数据丢失：原 `crawl-cache/pages/` 与 `assets/` 中物化数据删除后无法恢复（但 `documents.content` 完整保留，RAG 不受影响）
