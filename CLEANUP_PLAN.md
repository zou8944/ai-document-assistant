# 项目清理计划

## 📋 需要删除的文件和目录

### 根目录
- ❌ `claude-code-full-guide/` - Claude Code 示例指南 (136KB)
- ❌ `examples/` - 示例文件
- ❌ `PRPs/` - 项目需求文档 (68KB)
- ❌ `prePRPs/` - 预需求文档 (12KB)
- ❌ `ai-document-assistant.code-workspace` - VS Code workspace 配置 (已有 .vscode/)
- ❌ `qdrant_data/` - 旧的 Qdrant 数据 (已改用 Chroma)

### Backend 目录
- ❌ `backend/build/` - PyInstaller 构建缓存
- ❌ `backend/dist/` - PyInstaller 打包产物 (79MB!)
- ❌ `backend/build.spec` - PyInstaller 配置 (不再需要)
- ❌ `backend/chroma_db/` - 本地 Chroma 数据 (Docker 环境不需要)
- ❌ `backend/data/` - 本地应用数据 (Docker 环境不需要)
- ❌ `backend/logs/` - 本地日志文件 (Docker 环境不需要)
- ❌ `backend/__pycache__/` - Python 缓存
- ❌ `backend/.pytest_cache/` - Pytest 缓存
- ❌ `backend/.ruff_cache/` - Ruff 缓存
- ❌ `backend/.DS_Store` - macOS 系统文件
- ❌ `backend/docs/` - 空目录

### Frontend 目录
- ❌ `frontend/release/` - Electron 打包产物 (330MB!)
- ❌ `frontend/dist/` - 构建产物 (Docker 会重新构建)
- ❌ `frontend/src/main.ts` - Electron 主进程文件
- ❌ `frontend/src/preload.ts` - Electron 预加载脚本
- ❌ `frontend/tsconfig.main.json` - Electron 主进程 TS 配置
- ❌ `frontend/.DS_Store` - macOS 系统文件

## ✅ 需要保留的文件

### 根目录配置
- ✓ `.vscode/` - VS Code 配置 (已更新)
- ✓ `.gitignore` - Git 忽略配置
- ✓ `.env.example` - 环境变量模板
- ✓ `docker-compose.yml` - Docker 编排
- ✓ 所有 `.md` 文档

### Backend
- ✓ 所有源代码目录
- ✓ `.venv/` - Python 虚拟环境
- ✓ `pyproject.toml` - 项目配置
- ✓ `uv.lock` - 依赖锁定

### Frontend
- ✓ `src/` - 源代码
- ✓ `node_modules/` - NPM 依赖
- ✓ `package.json` - 项目配置
- ✓ 其他配置文件

## 📊 清理效果

预计释放空间：
- backend/dist: ~79MB
- frontend/release: ~330MB
- backend/chroma_db: ~27MB
- backend/data: ~5.5MB
- **总计: ~440MB+**

## ⚠️ 注意事项

1. **数据库文件**: `backend/chroma_db/` 和 `backend/data/` 包含本地数据库，删除后无法恢复
2. **构建产物**: 删除后可通过 Docker 或本地构建重新生成
3. **.gitignore**: 已更新，这些文件不会被提交到 Git
