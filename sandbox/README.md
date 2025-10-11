# Proteus AI 沙箱环境

欢迎来到 Proteus AI 沙箱环境！这是一个专为开发和测试 AI 代理（Agent）功能而设计的独立工作区。本环境提供了一个隔离的平台，您可以在其中安全地构建、实验和迭代您的 AI 代理。

## 快速开始

### 环境要求

在开始之前，请确保您的系统满足以下要求：

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.12+

### 安装与启动

请按照以下步骤设置并启动沙箱环境：

1.  **配置环境变量**：
    复制示例环境配置文件并根据您的需求进行修改。
    ```bash
    cp .env.example .env
    ```
    根据您的具体需求编辑 `.env` 文件。

2.  **构建并启动服务**：
    使用 Docker Compose 构建并启动所有必要的服务。
    ```bash
    docker-compose up -d --build
    ```

## 项目结构

```
sandbox/
├── app/                  # 应用代码
│   ├── main.py           # 主程序入口
│   └── sandbox.py        # 沙箱功能实现
├── docker-compose.yml    # Docker Compose配置
├── Dockerfile            # Docker构建文件
├── requirements.txt      # Python依赖
└── .env.example          # 环境变量示例
```

## 开发说明

### 代码修改与容器重建

在对代码进行任何修改后，您需要重新构建并启动 Docker 容器以使更改生效：

```bash
docker-compose up -d --build
```

### 查看服务日志

要实时查看所有服务的日志输出，可以使用以下命令：

```bash
docker-compose logs -f
```

### 运行测试

如果您的项目包含测试，您可以使用以下命令运行它们（请根据实际的测试框架和配置进行调整，例如 `pytest`）：

```bash
docker-compose exec app python -m pytest
```

## 许可证

本项目遵循 [Proteus AI](https://github.com/proteus-ai) 项目所使用的许可证。详情请参阅 Proteus AI 主仓库中的 `LICENSE` 文件。