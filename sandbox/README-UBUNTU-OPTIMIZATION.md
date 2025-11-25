# 沙箱系统 Ubuntu 基础镜像优化指南

## 概述

本项目提供了基于 Ubuntu 基础镜像的沙箱系统优化方案，包括多种 Docker 构建策略和安全加固配置。

## 优化方案对比

### 1. 基础 Ubuntu 镜像 (Dockerfile.ubuntu)
- **特点**: 单阶段构建，易于理解和维护
- **镜像大小**: ~500MB
- **安全性**: 中等，包含基本的安全配置
- **适用场景**: 开发环境、测试环境

### 2. 多阶段构建镜像 (Dockerfile.multistage) 
- **特点**: 两阶段构建，最小化运行时镜像
- **镜像大小**: ~300MB
- **安全性**: 高，包含完整的安全加固
- **适用场景**: 生产环境

### 3. 原始 Slim 镜像 (Dockerfile)
- **特点**: 基于 python:3.12-slim
- **镜像大小**: ~200MB
- **安全性**: 基础
- **适用场景**: 快速原型开发

## 构建选项

### 使用构建脚本

```bash
# 给予执行权限
chmod +x build.sh

# 构建基础 Ubuntu 镜像
./build.sh -t ubuntu -n my-sandbox -v 1.0

# 构建多阶段优化镜像
./build.sh -t multistage --no-cache --test

# 构建原始 Slim 镜像
./build.sh -t slim -n sandbox-dev
```

### 手动构建

```bash
# 基础 Ubuntu 镜像
docker build -t sandbox:ubuntu -f Dockerfile.ubuntu .

# 多阶段构建
docker build -t sandbox:multistage -f Dockerfile.multistage .

# 原始 Slim 镜像
docker build -t sandbox:slim .
```

## 安全加固特性

### 1. 非 Root 用户运行
```dockerfile
RUN groupadd -r sandbox && useradd -r -g sandbox -s /bin/bash sandbox
USER sandbox
```

### 2. 文件系统权限控制
- 限制临时目录访问权限
- 设置安全的 umask
- 分离数据、日志和代码目录

### 3. 资源限制
```dockerfile
# 限制进程数和文件描述符
RUN echo "sandbox hard nproc 100" >> /etc/security/limits.conf
RUN echo "sandbox hard nofile 100" >> /etc/security/limits.conf
```

### 4. 健康检查
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/docs || exit 1
```

## 性能优化

### 1. 构建优化
- 使用多阶段构建减少镜像大小
- 合理安排 Dockerfile 指令顺序
- 清理 apt 缓存和临时文件

### 2. 运行时优化
- 设置 Python 环境变量优化性能
- 使用虚拟环境隔离依赖
- 配置合适的 worker 数量

### 3. 依赖优化
- 移除不必要的依赖包
- 使用固定版本避免冲突
- 分离构建时和运行时依赖

## 部署指南

### 1. 开发环境
```bash
docker run -d -p 8000:8000 \
  -e API_KEY=your-secret-key \
  sandbox:ubuntu
```

### 2. 生产环境
```bash
docker run -d -p 8000:8000 \
  --name sandbox-prod \
  --restart unless-stopped \
  --memory=512m \
  --cpus=1 \
  -e API_KEY=your-secret-key \
  -v /host/logs:/var/logs/sandbox \
  -v /host/data:/var/data/sandbox \
  sandbox:multistage
```

### 3. Kubernetes 部署
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sandbox
spec:
  replicas: 2
  selector:
    matchLabels:
      app: sandbox
  template:
    metadata:
      labels:
        app: sandbox
    spec:
      containers:
      - name: sandbox
        image: sandbox:multistage
        ports:
        - containerPort: 8000
        env:
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: sandbox-secrets
              key: api-key
        resources:
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /docs
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

## 监控和日志

### 1. 日志配置
- 应用日志: `/var/logs/sandbox/sandbox.log`
- 访问日志: 标准输出
- 错误日志: 标准错误

### 2. 健康监控
```bash
# 检查容器健康状态
docker inspect --format='{{.State.Health.Status}}' container_name

# 查看健康检查日志
docker logs container_name
```

## 故障排除

### 1. 构建问题
```bash
# 清理构建缓存
docker system prune -f

# 重新构建不使用缓存
./build.sh --no-cache
```

### 2. 运行时问题
```bash
# 检查容器日志
docker logs container_name

# 进入容器调试
docker exec -it container_name bash

# 检查健康状态
docker inspect container_name | jq '.[].State.Health'
```

### 3. 性能问题
```bash
# 监控资源使用
docker stats container_name

# 检查进程
docker top container_name
```

## 最佳实践

1. **安全第一**: 始终使用非 root 用户运行容器
2. **资源限制**: 为生产环境设置内存和 CPU 限制
3. **版本控制**: 使用固定版本的镜像标签
4. **监控告警**: 设置健康检查和监控告警
5. **定期更新**: 定期更新基础镜像和安全补丁

## 联系方式

如有问题或建议，请联系开发团队。