#!/bin/bash

# 沙箱系统构建脚本
# 支持多种构建选项的优化构建脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助信息
show_help() {
    echo "沙箱系统构建脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -t, --type TYPE     构建类型: ubuntu (默认), multistage, slim"
    echo "  -n, --name NAME     镜像名称 (默认: proteus-sandbox)"
    echo "  -v, --version VER   镜像版本 (默认: latest)"
    echo "  --no-cache          构建时不使用缓存"
    echo "  --push              构建后推送到仓库"
    echo "  --test              构建后运行测试"
    echo "  -h, --help          显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 -t multistage -n my-sandbox -v 1.0"
    echo "  $0 --type ubuntu --no-cache --test"
}

# 默认参数
BUILD_TYPE="ubuntu"
IMAGE_NAME="proteus-sandbox"
IMAGE_VERSION="latest"
NO_CACHE=""
PUSH_IMAGE=false
RUN_TEST=false

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            BUILD_TYPE="$2"
            shift 2
            ;;
        -n|--name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        -v|--version)
            IMAGE_VERSION="$2"
            shift 2
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --push)
            PUSH_IMAGE=true
            shift
            ;;
        --test)
            RUN_TEST=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 验证构建类型
case $BUILD_TYPE in
    ubuntu|multistage|slim|optimized)
        ;;
    *)
        log_error "不支持的构建类型: $BUILD_TYPE"
        log_info "支持的构建类型: ubuntu, multistage, slim, optimized"
        exit 1
        ;;
esac

# 设置Dockerfile路径
case $BUILD_TYPE in
    ubuntu)
        DOCKERFILE="Dockerfile.ubuntu"
        ;;
    multistage)
        DOCKERFILE="Dockerfile.multistage"
        ;;
    slim)
        DOCKERFILE="Dockerfile"
        ;;
esac

FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_VERSION}"

log_info "开始构建沙箱镜像..."
log_info "构建类型: $BUILD_TYPE"
log_info "镜像名称: $FULL_IMAGE_NAME"
log_info "Dockerfile: $DOCKERFILE"

# 检查Dockerfile是否存在
if [ ! -f "$DOCKERFILE" ]; then
    log_error "Dockerfile不存在: $DOCKERFILE"
    exit 1
fi

# 构建镜像
log_info "执行Docker构建命令..."
docker build $NO_CACHE -t "$FULL_IMAGE_NAME" -f "$DOCKERFILE" .

if [ $? -eq 0 ]; then
    log_success "镜像构建成功: $FULL_IMAGE_NAME"
else
    log_error "镜像构建失败"
    exit 1
fi

# 显示镜像信息
log_info "镜像信息:"
docker images | grep "$IMAGE_NAME"

# 运行测试（如果启用）
if [ "$RUN_TEST" = true ]; then
    log_info "运行容器测试..."
    
    # 启动测试容器
    TEST_CONTAINER_NAME="sandbox-test-$$"
    docker run -d --name "$TEST_CONTAINER_NAME" -p 8000:8000 "$FULL_IMAGE_NAME"
    
    # 等待服务启动
    sleep 10
    
    # 测试健康检查
    if curl -f http://localhost:8000/docs > /dev/null 2>&1; then
        log_success "服务健康检查通过"
    else
        log_error "服务健康检查失败"
        docker logs "$TEST_CONTAINER_NAME"
        docker stop "$TEST_CONTAINER_NAME" > /dev/null
        docker rm "$TEST_CONTAINER_NAME" > /dev/null
        exit 1
    fi
    
    # 清理测试容器
    docker stop "$TEST_CONTAINER_NAME" > /dev/null
    docker rm "$TEST_CONTAINER_NAME" > /dev/null
    log_success "容器测试完成"
fi

# 推送镜像（如果启用）
if [ "$PUSH_IMAGE" = true ]; then
    log_info "推送镜像到仓库..."
    docker push "$FULL_IMAGE_NAME"
    
    if [ $? -eq 0 ]; then
        log_success "镜像推送成功"
    else
        log_error "镜像推送失败"
        exit 1
    fi
fi

log_success "沙箱系统构建完成!"
echo ""
echo "使用说明:"
echo "  运行容器: docker run -d -p 8000:8000 $FULL_IMAGE_NAME"
echo "  查看日志: docker logs <container_id>"
echo "  停止容器: docker stop <container_id>"