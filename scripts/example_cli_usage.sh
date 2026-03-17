#!/bin/bash
# 示例：如何使用 vmctl CLI 工具
# x-qemu-kvm CLI 使用示例脚本

set -e  # 遇到错误时退出

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

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "命令 '$1' 未找到"
        return 1
    fi
    return 0
}

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --help, -h        显示此帮助信息"
    echo "  --skip-setup      跳过环境检查"
    echo "  --skip-cleanup    跳过清理步骤"
    echo ""
    echo "示例:"
    echo "  $0                运行完整示例"
    echo "  $0 --skip-setup   跳过环境检查"
}

# 解析命令行参数
SKIP_SETUP=false
SKIP_CLEANUP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --skip-setup)
            SKIP_SETUP=true
            shift
            ;;
        --skip-cleanup)
            SKIP_CLEANUP=true
            shift
            ;;
        *)
            log_error "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

# 标题
echo "=========================================================="
echo "          x-qemu-kvm CLI 工具使用示例"
echo "=========================================================="
echo ""

# 步骤1: 环境检查
if [ "$SKIP_SETUP" = false ]; then
    log_info "步骤1: 检查环境..."

    # 检查 uv 命令
    if check_command "uv"; then
        log_success "找到 uv 命令"
    else
        log_error "未找到 uv 命令，请安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi

    # 检查 vmctl 命令
    if check_command "vmctl"; then
        log_success "找到 vmctl 命令"
    else
        log_warning "未找到 vmctl 命令，使用 uv run vmctl"
        VMCTL_CMD="uv run vmctl"
    fi

    # 设置默认命令
    VMCTL_CMD=${VMCTL_CMD:-"vmctl"}

    # 检查 libvirt 服务
    if systemctl is-active --quiet libvirtd; then
        log_success "libvirtd 服务正在运行"
    else
        log_warning "libvirtd 服务未运行，某些功能可能受限"
    fi

    log_success "环境检查完成"
    echo ""
fi

# 步骤2: 显示版本信息
log_info "步骤2: 显示版本信息..."
$VMCTL_CMD version
echo ""

# 步骤3: 检查配置
log_info "步骤3: 检查当前配置..."
$VMCTL_CMD config
echo ""

# 步骤4: 列出当前虚拟机
log_info "步骤4: 列出当前所有虚拟机..."
$VMCTL_CMD vm list --all
echo ""

# 步骤5: 检查环境
log_info "步骤5: 检查环境..."
$VMCTL_CMD check
echo ""

# 步骤6: 创建示例虚拟机（交互式）
log_info "步骤6: 创建示例虚拟机..."
log_warning "注意: 以下步骤需要实际虚拟化环境支持"
echo ""

# 询问是否继续
read -p "是否继续创建虚拟机示例？(y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "跳过虚拟机创建示例"
    echo ""
    log_success "示例脚本执行完成（跳过虚拟机操作）"
    exit 0
fi

# 虚拟机配置
VM_NAME="demo-vm-$(date +%s)"
DISK_PATH="/tmp/${VM_NAME}.qcow2"
ISO_PATH=""  # 可选: 设置为实际的 ISO 路径

log_info "虚拟机配置:"
echo "  名称: $VM_NAME"
echo "  磁盘: $DISK_PATH"
echo "  ISO: ${ISO_PATH:-无}"

# 检查磁盘文件是否存在
if [ -f "$DISK_PATH" ]; then
    log_warning "磁盘文件已存在: $DISK_PATH"
    read -p "是否删除现有文件？(y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f "$DISK_PATH"
        log_success "已删除现有磁盘文件"
    fi
fi

# 创建磁盘文件（示例）
log_info "创建示例磁盘文件..."
qemu-img create -f qcow2 "$DISK_PATH" 2G 2>/dev/null || {
    log_warning "无法创建磁盘文件，跳过虚拟机创建"
    DISK_PATH="/var/lib/libvirt/images/${VM_NAME}.qcow2"
    log_info "使用默认路径: $DISK_PATH"
}

# 创建虚拟机
log_info "创建虚拟机: $VM_NAME"
if [ -n "$ISO_PATH" ] && [ -f "$ISO_PATH" ]; then
    $VMCTL_CMD vm create \
        --name "$VM_NAME" \
        --memory 1024 \
        --vcpu 2 \
        --disk "$DISK_PATH" \
        --format qcow2 \
        --iso "$ISO_PATH" \
        --network default \
        --description "示例虚拟机，由脚本创建"
else
    $VMCTL_CMD vm create \
        --name "$VM_NAME" \
        --memory 1024 \
        --vcpu 2 \
        --disk "$DISK_PATH" \
        --format qcow2 \
        --network default \
        --description "示例虚拟机，由脚本创建" \
        --no-confirm
fi

if [ $? -eq 0 ]; then
    log_success "虚拟机创建命令已提交"
else
    log_error "虚拟机创建失败"
fi

echo ""

# 步骤7: 查看虚拟机详情
log_info "步骤7: 查看虚拟机详情..."
$VMCTL_CMD vm info "$VM_NAME"
echo ""

# 步骤8: 启动虚拟机
log_info "步骤8: 启动虚拟机..."
read -p "是否启动虚拟机？(y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    $VMCTL_CMD vm start "$VM_NAME"
    if [ $? -eq 0 ]; then
        log_success "虚拟机启动成功"

        # 等待一会儿
        sleep 3

        # 再次查看状态
        log_info "查看启动后的状态..."
        $VMCTL_CMD vm info "$VM_NAME"
    else
        log_error "虚拟机启动失败"
    fi
else
    log_info "跳过虚拟机启动"
fi

echo ""

# 步骤9: 列出虚拟机（查看状态变化）
log_info "步骤9: 列出虚拟机（查看状态变化）..."
$VMCTL_CMD vm list --all
echo ""

# 步骤10: 停止虚拟机
log_info "步骤10: 停止虚拟机..."
read -p "是否停止虚拟机？(y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    $VMCTL_CMD vm stop "$VM_NAME"
    if [ $? -eq 0 ]; then
        log_success "虚拟机停止成功"
    else
        log_error "虚拟机停止失败"
    fi
else
    log_info "跳过虚拟机停止"
fi

echo ""

# 步骤11: 删除虚拟机
if [ "$SKIP_CLEANUP" = false ]; then
    log_info "步骤11: 清理虚拟机..."
    read -p "是否删除虚拟机？(y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # 询问是否删除磁盘
        read -p "是否同时删除磁盘文件？(y/N): " -n 1 -r
        echo ""
        DELETE_DISK=""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            DELETE_DISK="--delete-disk"
            log_warning "将删除磁盘文件: $DISK_PATH"
        fi

        $VMCTL_CMD vm delete "$VM_NAME" $DELETE_DISK --force
        if [ $? -eq 0 ]; then
            log_success "虚拟机删除成功"
        else
            log_error "虚拟机删除失败"
        fi
    else
        log_info "保留虚拟机: $VM_NAME"
        log_warning "请手动清理虚拟机资源"
    fi
else
    log_info "跳过清理步骤，虚拟机保留: $VM_NAME"
fi

echo ""

# 最终状态
log_info "最终状态:"
$VMCTL_CMD vm list --all

echo ""
log_success "示例脚本执行完成！"
echo ""
log_info "了解更多:"
echo "  文档: vmctl docs"
echo "  帮助: vmctl --help"
echo "  VM命令: vmctl vm --help"
echo ""

# 显示创建的虚拟机信息
if [ "$SKIP_CLEANUP" = false ] || [ "$SKIP_CLEANUP" = true -a "$VM_NAME" != "" ]; then
    echo "创建的虚拟机:"
    echo "  名称: $VM_NAME"
    echo "  磁盘: $DISK_PATH"
    echo ""
    log_warning "注意: 如果虚拟机未被删除，请手动管理资源"
fi