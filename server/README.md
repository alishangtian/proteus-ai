# 轻量级 Conversation 访问 WebServer

基于 FastAPI 的轻量级 Web 服务器，提供对话相关接口和任务提交功能。

## 功能特性

- **认证方式**：Bearer Token (beartoken 模式)，兼容 Session Cookie
- **对话管理**：
  - `GET /conversations` – 获取当前用户的会话列表
  - `GET /conversations/{conversation_id}` – 获取指定会话的详细信息
- **模型配置**：
  - `GET /models` – 获取可用的模型列表（从 `conf/models_config.yaml` 读取）
- **重放流**：
  - `GET /replay/stream/{chat_id}` – SSE 流式重放已保存的聊天记录
- **任务提交**：
  - `POST /submit_task` – 提交任务到 Redis 队列（参数与 `/chat` 接口一致）
- **健康检查**：
  - `GET /health` – 服务健康状态

## 快速开始

### 环境要求

- Python 3.8+
- Redis 服务器（用于会话存储和任务队列）

### 安装依赖

```bash
cd proteus-ai/server
pip install -r requirements.txt
```

### 配置环境变量

复制 `.env.example` 并修改：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
SESSION_MODEL=redis
```

### 运行服务器

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

服务将在 http://localhost:8000 启动。

### API 文档

启动后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 认证方式

### Bearer Token

在请求头中添加：

```
Authorization: Bearer <your_token>
```

Token 可通过原系统的 `/token` 接口获取。

### Session Cookie（兼容）

如果未提供 Bearer Token，将尝试从 `session` cookie 读取会话。

## 任务队列

`/submit_task` 接口将任务数据序列化为 JSON 并推送到 Redis 的 `task_queue` 列表。任务负载包含所有 `/chat` 接口参数以及提交者的 token 和用户名。

消费者可以从 `task_queue` 中取出任务进行处理。

## 项目结构

```
server/
├── main.py              # 主应用，包含所有端点
├── requirements.txt     # Python 依赖
├── README.md           # 本文档
└── .env.example        # 环境变量示例
```

## 注意事项

- 本服务依赖 Redis 存储会话、对话数据和任务队列，请确保 Redis 服务可用。
- `/models` 端点需要在项目根目录或上级目录中存在 `conf/models_config.yaml` 文件。
- 重放流功能需要 Redis 中已保存的聊天记录（key 格式：`chat_stream:{chat_id}`）。

## 许可证

MIT
