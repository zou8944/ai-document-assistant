# 调试指南

## 🐛 开发调试模式

### 方式 1: 本地开发模式 (推荐用于调试)

这是最方便的调试方式，可以使用 IDE 的调试器和热重载。

#### 1. 启动 Chroma 向量数据库
```bash
docker run -d -p 8000:8000 --name chroma chromadb/chroma:latest
```

#### 2. 调试后端 (Python)

##### 使用 VS Code 调试
创建 `.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI Backend",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "api.main:app",
        "--reload",
        "--host",
        "127.0.0.1",
        "--port",
        "8888"
      ],
      "cwd": "${workspaceFolder}/backend",
      "env": {
        "PYTHONPATH": "${workspaceFolder}/backend",
        "CRAWL_API_KEY": "your_api_key_here",
        "CRAWL_BASE_URL": "https://api.siliconflow.cn/v1",
        "AGENT_API_KEY": "your_anthropic_api_key_here",
        "EMBEDDING_API_KEY": "your_api_key_here",
        "EMBEDDING_BASE_URL": "https://api.openai.com/v1"
      },
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

##### 命令行调试
```bash
cd backend

# 设置环境变量
export CRAWL_API_KEY="your_api_key_here"
export CRAWL_BASE_URL="https://api.siliconflow.cn/v1"
export AGENT_API_KEY="your_anthropic_api_key_here"
export EMBEDDING_API_KEY="your_api_key_here"
export EMBEDDING_BASE_URL="https://api.openai.com/v1"

# 启动开发服务器 (带自动重载)
uv run uvicorn api.main:app --reload --host 127.0.0.1 --port 8888

# 或使用 api_server.py
uv run python api_server.py
```

##### Python 断点调试
在代码中添加断点:
```python
# 方式 1: pdb 调试器
import pdb; pdb.set_trace()

# 方式 2: breakpoint() (Python 3.7+)
breakpoint()

# 方式 3: VS Code 直接打断点
# 在行号左侧点击添加红点
```

#### 3. 调试前端 (React)

##### 使用 VS Code 调试
创建 `.vscode/launch.json` (前端部分):
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "React: Chrome Debug",
      "type": "chrome",
      "request": "launch",
      "url": "http://localhost:5173",
      "webRoot": "${workspaceFolder}/frontend/src",
      "sourceMapPathOverrides": {
        "webpack:///src/*": "${webRoot}/*"
      }
    }
  ]
}
```

##### 命令行启动
```bash
cd frontend

# 安装依赖 (首次)
npm install

# 启动开发服务器 (带热重载)
npm run dev

# 访问 http://localhost:5173
```

##### 浏览器调试
1. 打开浏览器开发者工具 (F12)
2. **Console** 标签: 查看日志输出
3. **Network** 标签: 查看 API 请求
4. **Sources** 标签: 设置断点调试
5. **React DevTools**: 查看组件状态

##### 使用 console.log 调试
```typescript
// 在代码中添加日志
console.log('Debug info:', variable)
console.error('Error occurred:', error)
console.table(arrayData)  // 表格形式显示数组
```

##### 使用 debugger 语句
```typescript
// 在代码中添加断点
function myFunction() {
  debugger;  // 浏览器会在这里暂停
  // ... 代码
}
```

### 方式 2: Docker + 远程调试

适合调试 Docker 环境特定的问题。

#### 后端远程调试

修改 `backend/Dockerfile` 添加调试支持:
```dockerfile
# 开发环境添加调试工具
RUN uv add --dev debugpy

# 暴露调试端口
EXPOSE 5678
```

修改 `docker-compose.yml`:
```yaml
services:
  backend:
    command: uv run python -m debugpy --listen 0.0.0.0:5678 api_server.py --host 0.0.0.0 --port 8888
    ports:
      - "8888:8888"
      - "5678:5678"  # 调试端口
```

VS Code 配置:
```json
{
  "name": "Python: Remote Attach",
  "type": "python",
  "request": "attach",
  "connect": {
    "host": "localhost",
    "port": 5678
  },
  "pathMappings": [
    {
      "localRoot": "${workspaceFolder}/backend",
      "remoteRoot": "/app"
    }
  ]
}
```

## 🔍 常见调试场景

### 1. API 请求失败

#### 检查网络请求
```bash
# 使用 curl 测试 API
curl -v http://localhost:8888/api/v1/health

# 测试文件上传
curl -X POST http://localhost:8888/api/v1/files/upload \
  -F "file=@test.pdf"

# 查看详细请求信息
curl -v -H "Content-Type: application/json" \
  http://localhost:8888/api/v1/collections
```

#### 浏览器网络面板
1. 打开 DevTools → Network
2. 重现问题
3. 查看失败的请求
4. 检查请求头、请求体、响应

#### 后端日志
```bash
# 本地开发模式
cd backend
tail -f ~/.ai-document-assistant/backend.log

# Docker 模式
docker-compose logs -f backend
```

### 2. CORS 错误

#### 检查 CORS 配置
```python
# backend/api/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发时允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### 临时解决方案
浏览器启动时禁用 CORS:
```bash
# Chrome (macOS)
open -na "Google Chrome" --args --disable-web-security --user-data-dir=/tmp/chrome_dev

# Chrome (Windows)
chrome.exe --disable-web-security --user-data-dir="C:\tmp\chrome_dev"
```

### 3. 向量搜索问题

#### 检查 Chroma 连接
```bash
# 本地模式
curl http://localhost:8000/api/v1/heartbeat

# Docker 模式
docker-compose exec backend curl http://chroma:8000/api/v1/heartbeat
```

#### 查看 Chroma 数据
```python
# 在后端代码中添加调试
from vector_store.chroma_client import create_chroma_manager

manager = create_chroma_manager()
collection = await manager.get_collection("collection_name")
print(f"Collection count: {collection.count()}")
```

### 4. 环境变量问题

#### 检查环境变量是否生效
```python
# 在后端代码中添加
import os
print("CRAWL_API_KEY:", os.getenv("CRAWL_API_KEY", "NOT SET"))
print("AGENT_API_KEY:", os.getenv("AGENT_API_KEY", "NOT SET"))
print("EMBEDDING_API_KEY:", os.getenv("EMBEDDING_API_KEY", "NOT SET"))
print("CHROMA_HOST:", os.getenv("CHROMA_HOST", "NOT SET"))
```

```typescript
// 在前端代码中添加
console.log('API URL:', import.meta.env.VITE_API_URL)
```

#### Docker 环境变量
```bash
# 查看容器环境变量
docker-compose exec backend env | grep -E "CRAWL_|AGENT_|EMBEDDING_"

# 进入容器检查
docker-compose exec backend sh
echo $CRAWL_API_KEY
```

### 5. 前端状态问题

#### 使用 Zustand DevTools
```typescript
// 在 store 中启用 devtools
import { create } from 'zustand'
import { devtools } from 'zustand/middleware'

const useStore = create(
  devtools(
    (set) => ({
      // ... store state
    }),
    { name: 'AppStore' }
  )
)
```

#### React DevTools
1. 安装 React DevTools 浏览器扩展
2. 打开 DevTools → Components/Profiler
3. 查看组件树和状态
4. 追踪状态变化

### 6. 文件上传问题

#### 检查文件大小限制
```python
# backend/api/routes/documents.py
from fastapi import UploadFile, File

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    print(f"File: {file.filename}, Size: {file.size}")
    # 检查文件大小
    if file.size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=413, detail="File too large")
```

#### 前端调试
```typescript
// 查看文件对象
const handleFileUpload = (file: File) => {
  console.log('File info:', {
    name: file.name,
    size: file.size,
    type: file.type
  })
}
```

## 🛠️ 调试工具

### VS Code 扩展推荐

#### 后端 (Python)
- **Python** - 官方 Python 支持
- **Pylance** - 智能代码补全
- **Python Debugger** - 调试器
- **Python Test Explorer** - 测试运行器

#### 前端 (TypeScript/React)
- **ES7+ React/Redux/React-Native snippets** - 代码片段
- **ESLint** - 代码检查
- **Prettier** - 代码格式化
- **TypeScript Vue Plugin** - TypeScript 支持
- **React Developer Tools** - React 调试

#### 通用
- **Docker** - Docker 文件支持
- **REST Client** - API 测试
- **GitLens** - Git 增强
- **Error Lens** - 错误高亮

### 浏览器扩展
- **React Developer Tools** - React 组件调试
- **Redux DevTools** - Redux 状态管理
- **Vue.js devtools** - 通用开发工具
- **JSON Viewer** - JSON 格式化

### 命令行工具
```bash
# HTTP 客户端
brew install httpie
http GET http://localhost:8888/api/v1/health

# WebSocket 测试
npm install -g wscat
wscat -c ws://localhost:8888/ws

# 性能分析
npm install -g autocannon
autocannon -c 10 -d 30 http://localhost:8888/api/v1/health
```

## 📊 性能调试

### 后端性能

#### 使用 FastAPI 内置 profiler
```python
from fastapi import FastAPI
from fastapi.middleware.profiler import ProfilerMiddleware

app = FastAPI()
app.add_middleware(ProfilerMiddleware)
```

#### cProfile 分析
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# 执行代码
result = expensive_function()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

#### 内存分析
```python
from memory_profiler import profile

@profile
def memory_intensive_function():
    # 代码
    pass
```

### 前端性能

#### React Profiler
```typescript
import { Profiler } from 'react'

function onRenderCallback(
  id, phase, actualDuration, baseDuration,
  startTime, commitTime, interactions
) {
  console.log(`${id} took ${actualDuration}ms`)
}

<Profiler id="App" onRender={onRenderCallback}>
  <App />
</Profiler>
```

#### Chrome DevTools Performance
1. 打开 DevTools → Performance
2. 点击录制按钮
3. 执行操作
4. 停止录制
5. 分析火焰图

## 🔧 配置文件

### 完整的 VS Code workspace 配置

创建 `.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/backend/.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter",
    "editor.formatOnSave": true
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  }
}
```

### 多配置调试

创建 `.vscode/launch.json` (完整版):
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Backend: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "api.main:app",
        "--reload",
        "--host", "127.0.0.1",
        "--port", "8888"
      ],
      "cwd": "${workspaceFolder}/backend",
      "env": {
        "PYTHONPATH": "${workspaceFolder}/backend"
      },
      "console": "integratedTerminal"
    },
    {
      "name": "Frontend: Chrome",
      "type": "chrome",
      "request": "launch",
      "url": "http://localhost:5173",
      "webRoot": "${workspaceFolder}/frontend/src"
    },
    {
      "name": "Backend: Docker Attach",
      "type": "python",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      },
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}/backend",
          "remoteRoot": "/app"
        }
      ]
    }
  ],
  "compounds": [
    {
      "name": "Full Stack Debug",
      "configurations": ["Backend: FastAPI", "Frontend: Chrome"]
    }
  ]
}
```

## 💡 调试技巧

### 1. 日志级别控制
```python
# backend/config.py
import logging

# 开发时使用 DEBUG
logging.basicConfig(level=logging.DEBUG)

# 生产时使用 INFO
logging.basicConfig(level=logging.INFO)
```

### 2. 条件断点
```python
# VS Code: 右键断点 → Edit Breakpoint → 添加条件
# 例如: user_id == "123"

# 代码中:
if user_id == "123":
    breakpoint()  # 只在特定条件下触发
```

### 3. 请求跟踪
```python
# 添加请求 ID 追踪
import uuid
from fastapi import Request

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

### 4. 数据库查询调试
```python
# 启用 SQL 日志
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

## 📚 更多资源

- [FastAPI 调试文档](https://fastapi.tiangolo.com/tutorial/debugging/)
- [React DevTools 指南](https://react.dev/learn/react-developer-tools)
- [Chrome DevTools 文档](https://developer.chrome.com/docs/devtools/)
- [VS Code 调试指南](https://code.visualstudio.com/docs/editor/debugging)

---

**提示**: 遇到问题时,先查看日志,再使用断点调试,最后考虑添加更详细的日志输出。
