# 调试快速指南

## 🚀 最快调试方式 (推荐)

### 方式 1: VS Code 一键调试

1. **打开 VS Code**
2. **按 F5** 或点击调试按钮
3. **选择配置**:
   - `Backend: FastAPI Dev Server` - 调试后端
   - `Frontend: Chrome Debug` - 调试前端
   - `Full Stack: Backend + Frontend` - 同时调试

就这么简单！已经为你配置好了所有调试设置。

### 方式 2: 命令行调试

```bash
# 终端 1: 启动 Chroma
docker run -d -p 8000:8000 --name chroma chromadb/chroma:latest

# 终端 2: 启动后端 (支持断点和热重载)
cd backend
export OPENAI_API_KEY="your_key"
uv run python api_server.py

# 终端 3: 启动前端 (支持热重载)
cd frontend
npm run dev

# 浏览器访问: http://localhost:5173
```

## 🔍 常见调试需求

### 查看 API 请求/响应
1. 打开浏览器 DevTools (F12)
2. 切换到 **Network** 标签
3. 执行操作,查看请求

### 查看后端日志
```bash
# 本地开发
tail -f ~/.ai-document-assistant/backend.log

# Docker 部署
docker-compose logs -f backend
```

### 前端断点调试
1. 打开 Chrome DevTools (F12)
2. 切换到 **Sources** 标签
3. 在代码中点击行号添加断点
4. 或在代码中添加 `debugger;`

### 后端断点调试 (VS Code)
1. 在 Python 文件中点击行号左侧添加红点
2. 按 F5 启动调试
3. 程序会在断点处暂停

### 测试 API
```bash
# 健康检查
curl http://localhost:8888/api/v1/health

# 获取集合列表
curl http://localhost:8888/api/v1/collections

# 详细请求信息
curl -v http://localhost:8888/api/v1/health
```

## 🛠️ VS Code 任务

按 `Cmd+Shift+P` (Mac) 或 `Ctrl+Shift+P` (Windows/Linux), 输入 "Tasks: Run Task":

- **Backend: Start Dev Server** - 启动后端
- **Frontend: Start Dev Server** - 启动前端
- **Backend: Run Tests** - 运行后端测试
- **Docker: Up** - 启动 Docker 服务
- **Docker: Logs (Backend)** - 查看后端日志

## 📝 添加日志调试

### Python (后端)
```python
import logging
logger = logging.getLogger(__name__)

# 在代码中添加
logger.debug(f"Debug info: {variable}")
logger.info(f"Info: {data}")
logger.error(f"Error: {error}")
```

### TypeScript (前端)
```typescript
// 在代码中添加
console.log('Debug info:', variable)
console.error('Error:', error)
console.table(arrayData)  // 表格显示
```

## 🐳 Docker 环境调试

```bash
# 查看所有容器状态
docker-compose ps

# 查看后端日志
docker-compose logs -f backend

# 进入后端容器
docker-compose exec backend sh

# 重启后端服务
docker-compose restart backend

# 查看环境变量
docker-compose exec backend env | grep OPENAI
```

## ⚡ 热重载说明

- **后端**: 修改 Python 代码自动重启 (uvicorn --reload)
- **前端**: 修改 React 代码自动刷新 (Vite HMR)
- **Docker**: 需要重新构建镜像才能看到更改

## 🔧 性能调试

### 后端慢查询
```python
import time

start = time.time()
# 执行操作
result = expensive_function()
print(f"Took {time.time() - start:.2f}s")
```

### 前端性能
1. 打开 DevTools → Performance
2. 点击录制 (圆点)
3. 执行操作
4. 停止录制
5. 分析火焰图

## 📚 完整文档

详细调试指南请查看: [DEBUG_GUIDE.md](DEBUG_GUIDE.md)

## 💡 调试技巧

1. **先看日志**: 80% 的问题可以通过日志发现
2. **使用断点**: 复杂逻辑用断点单步执行
3. **网络面板**: API 问题先看 Network 标签
4. **隔离问题**: 先确定是前端还是后端的问题
5. **最小复现**: 找到最小可复现的步骤

---

**提示**: 遇到问题先查看日志,90% 的错误信息都在日志里! 🎯
