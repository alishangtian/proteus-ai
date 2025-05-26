# Proteus AI Sandbox 环境

Proteus AI 的沙箱环境，用于开发和测试AI代理相关功能。

## 环境要求

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.12+

## 安装步骤

1. 复制环境配置文件：
   ```bash
   cp .env.example .env
   ```
2. 根据需求修改 `.env` 文件中的配置

3. 构建并启动容器：
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

- 修改代码后需要重新构建容器：
  ```bash
  docker-compose up -d --build
  ```

- 查看日志：
  ```bash
  docker-compose logs -f
  ```

## 许可证

本项目使用 [Proteus AI](https://github.com/proteus-ai) 相同的许可证。