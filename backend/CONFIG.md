# 配置管理

AI Document Assistant 后端采用集中化的配置管理系统。所有配置都通过环境变量设置，并在启动时集中加载和验证。

## 配置类结构

配置系统基于 `config.py` 中的 `Config` 类，它提供：

- 🔧 **集中管理**：所有配置项在一个地方定义
- ✅ **自动验证**：启动时验证配置有效性  
- 🌍 **环境变量支持**：从环境变量自动加载
- 📝 **类型安全**：使用数据类提供类型提示

## 配置项

### 对话模型配置
```bash
OPENAI_API_KEY=your-chat-api-key         # 必需：对话模型 API 密钥
OPENAI_API_BASE=https://api.custom.com   # 可选：对话模型 API 端点
OPENAI_CHAT_MODEL=gpt-3.5-turbo          # 可选：对话模型名称  
```

### 嵌入模型配置（独立配置）
```bash
EMBEDDING_API_KEY=your-embedding-key     # 可选：嵌入模型 API 密钥（未设置时使用对话模型配置）
EMBEDDING_API_BASE=https://api.embed.com # 可选：嵌入模型 API 端点（未设置时使用对话模型配置）
EMBEDDING_MODEL=text-embedding-ada-002   # 可选：嵌入模型名称
```

### Qdrant 向量数据库配置
```bash
QDRANT_HOST=localhost     # Qdrant 服务器地址
QDRANT_PORT=6334          # Qdrant 服务器端口
```

### 文件处理配置
```bash
MAX_FILE_SIZE_MB=50.0     # 最大文件大小（MB）
```

### 文本处理配置
```bash
CHUNK_SIZE=1000           # 文本块大小
CHUNK_OVERLAP=200         # 文本块重叠大小
```

### 网络爬虫配置
```bash
CRAWLER_MAX_DEPTH=3       # 最大爬取深度
CRAWLER_DELAY=1.0         # 爬取延迟（秒）
CRAWLER_MAX_PAGES=50      # 最大爬取页面数
```

### 应用配置
```bash
LOG_LEVEL=INFO            # 日志级别
```

## 使用方法

### 1. 在代码中使用配置

```python
from config import get_config

# 获取全局配置实例
config = get_config()

# 使用配置项
print(f"Using model: {config.openai_chat_model}")
print(f"Chunk size: {config.chunk_size}")

# 获取 OpenAI 初始化参数
chat_kwargs = config.get_openai_chat_kwargs()
embeddings_kwargs = config.get_openai_embeddings_kwargs()
```

### 2. 设置环境变量

**方法 1：使用 .env 文件**
```bash
# 复制示例配置文件
cp .env.example .env

# 编辑配置文件
vim .env
```

**方法 2：直接设置环境变量**
```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_API_BASE="https://api.custom.com/v1"
```

**方法 3：在运行时设置**
```bash
OPENAI_API_KEY="your-key" uv run python main.py
```

## 服务提供商配置示例

### 1. 单一服务商（推荐）

#### 智谱 AI (GLM) - 支持对话和嵌入
```bash
OPENAI_API_KEY=your-zhipu-api-key
OPENAI_API_BASE=https://open.bigmodel.cn/api/paas/v4
OPENAI_CHAT_MODEL=glm-4
EMBEDDING_MODEL=embedding-2
```

#### 月之暗面 (Kimi)
```bash
OPENAI_API_KEY=your-kimi-api-key
OPENAI_API_BASE=https://api.moonshot.cn/v1
OPENAI_CHAT_MODEL=moonshot-v1-8k
EMBEDDING_MODEL=moonshot-v1-8k
```

### 2. 混合服务商配置

#### DeepSeek（对话）+ OpenAI（嵌入）
```bash
# 对话模型使用 DeepSeek
OPENAI_API_KEY=your-deepseek-api-key
OPENAI_API_BASE=https://api.deepseek.com
OPENAI_CHAT_MODEL=deepseek-chat

# 嵌入模型使用 OpenAI
EMBEDDING_API_KEY=your-openai-api-key
EMBEDDING_API_BASE=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-ada-002
```

#### DeepSeek（对话）+ 智谱（嵌入）
```bash
# 对话模型使用 DeepSeek
OPENAI_API_KEY=your-deepseek-api-key
OPENAI_API_BASE=https://api.deepseek.com
OPENAI_CHAT_MODEL=deepseek-chat

# 嵌入模型使用智谱
EMBEDDING_API_KEY=your-zhipu-api-key
EMBEDDING_API_BASE=https://open.bigmodel.cn/api/paas/v4
EMBEDDING_MODEL=embedding-2
```

### 3. 其他单一服务商

#### Azure OpenAI
```bash
OPENAI_API_KEY=your-azure-key
OPENAI_API_BASE=https://your-resource.openai.azure.com
OPENAI_CHAT_MODEL=gpt-35-turbo
EMBEDDING_MODEL=text-embedding-ada-002
```

## 配置验证

程序启动时会自动验证配置：

```python
# 验证必需配置
config.validate()  # 如果验证失败会抛出 ValueError
```

验证包括：
- ✅ OPENAI_API_KEY 必须设置
- ✅ QDRANT_PORT 必须为正整数
- ✅ 文件大小限制必须为正数
- ✅ 文本块配置合理性检查

## 最佳实践

1. **使用 .env 文件**：在本地开发时使用 `.env` 文件管理配置
2. **生产环境**：在生产环境中直接设置环境变量
3. **敏感信息**：API 密钥等敏感信息不要提交到版本控制
4. **配置验证**：依赖自动验证，不要跳过验证步骤
5. **类型安全**：利用配置类的类型提示获得更好的开发体验

## 故障排除

### 常见错误

**错误**：`Configuration validation failed: OPENAI_API_KEY is required but not set`
**解决**：设置 OPENAI_API_KEY 环境变量

**错误**：`Failed to initialize embeddings`
**解决**：检查 API 密钥和端点配置是否正确

**错误**：`QDRANT_PORT must be a positive integer`
**解决**：确保 QDRANT_PORT 设置为有效的端口号

### 调试配置

```python
from config import get_config

config = get_config()
print(f"Current configuration:")
print(f"  Chat Model: {config.openai_chat_model}")
print(f"  API Base: {config.openai_api_base}")
print(f"  Qdrant: {config.qdrant_host}:{config.qdrant_port}")
```