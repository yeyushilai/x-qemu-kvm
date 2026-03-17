"""
虚拟机数据模型

该模块定义了虚拟机的数据模型，包括：
- 虚拟机状态枚举
- 创建虚拟机的请求模型
- 虚拟机的响应模型
- 虚拟机详情模型
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


class VMStatus(str, Enum):
    """
    虚拟机状态枚举

    对应 libvirt 的域状态:
    - libvirt.VIR_DOMAIN_NOSTATE = 0
    - libvirt.VIR_DOMAIN_RUNNING = 1
    - libvirt.VIR_DOMAIN_BLOCKED = 2
    - libvirt.VIR_DOMAIN_PAUSED = 3
    - libvirt.VIR_DOMAIN_SHUTDOWN = 4
    - libvirt.VIR_DOMAIN_SHUTOFF = 5
    - libvirt.VIR_DOMAIN_CRASHED = 6
    - libvirt.VIR_DOMAIN_PMSUSPENDED = 7
    """

    NOSTATE = "nostate"          # 无状态
    RUNNING = "running"          # 运行中
    BLOCKED = "blocked"          # 阻塞
    PAUSED = "paused"            # 暂停
    SHUTDOWN = "shutdown"        # 关机中
    SHUTOFF = "shutoff"          # 已关机
    CRASHED = "crashed"          # 崩溃
    PMSUSPENDED = "pmsuspended"  # 电源管理挂起


class VMCreateRequest(BaseModel):
    """创建虚拟机请求模型"""

    name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="虚拟机名称",
        example="ubuntu-server",
        pattern=r"^[a-zA-Z0-9_.-]+$",
    )

    memory: int = Field(
        ...,
        gt=0,
        le=1048576,  # 最大 1TB
        description="内存大小 (MB)",
        example=2048,
    )

    vcpu: int = Field(
        ...,
        gt=0,
        le=1024,
        description="虚拟 CPU 数量",
        example=2,
    )

    disk_path: str = Field(
        ...,
        description="磁盘镜像路径",
        example="/var/lib/libvirt/images/ubuntu.qcow2",
    )

    disk_format: str = Field(
        default="qcow2",
        description="磁盘格式",
        example="qcow2",
        pattern=r"^(qcow2|raw|vmdk|vdi|vhd)$",
    )

    disk_size: Optional[int] = Field(
        default=None,
        gt=0,
        le=1099511627776,  # 最大 1TB
        description="磁盘大小 (MB)，如果为 None 则使用现有磁盘大小",
        example=20480,
    )

    iso_path: Optional[str] = Field(
        default=None,
        description="ISO 镜像路径（用于安装）",
        example="/var/lib/libvirt/isos/ubuntu-22.04.iso",
    )

    network: str = Field(
        default="default",
        description="网络名称",
        example="default",
    )

    graphics: bool = Field(
        default=False,
        description="是否启用图形显示（VNC/SPICE）",
    )

    graphics_port: Optional[int] = Field(
        default=None,
        ge=5900,
        le=65535,
        description="图形显示端口（如果启用）",
        example=5900,
    )

    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="虚拟机描述",
        example="Ubuntu 22.04 Server",
    )

    @validator("memory")
    def validate_memory(cls, v):
        """验证内存大小，建议为 2 的幂次方"""
        if v & (v - 1) != 0:  # 不是 2 的幂
            # 向上取整到最近的 2 的幂
            import math
            v = 2 ** math.ceil(math.log2(v))
        return v

    @validator("vcpu")
    def validate_vcpu(cls, v):
        """验证 CPU 数量，建议为 1, 2, 4, 8, ..."""
        if v <= 0:
            raise ValueError("vcpu 必须大于 0")
        return v

    @validator("disk_size")
    def validate_disk_size(cls, v, values):
        """验证磁盘大小"""
        if v is not None and v < 1024:  # 最小 1GB
            raise ValueError("磁盘大小至少为 1024 MB (1GB)")
        return v


class VMUpdateRequest(BaseModel):
    """更新虚拟机请求模型"""

    memory: Optional[int] = Field(
        default=None,
        gt=0,
        le=1048576,
        description="内存大小 (MB)",
        example=4096,
    )

    vcpu: Optional[int] = Field(
        default=None,
        gt=0,
        le=1024,
        description="虚拟 CPU 数量",
        example=4,
    )

    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="虚拟机描述",
        example="Updated description",
    )


class VMResponse(BaseModel):
    """虚拟机响应模型（基础信息）"""

    id: str = Field(..., description="虚拟机 ID (UUID)", example="123e4567-e89b-12d3-a456-426614174000")
    name: str = Field(..., description="虚拟机名称", example="ubuntu-server")
    status: VMStatus = Field(..., description="虚拟机状态", example=VMStatus.RUNNING)
    memory: int = Field(..., description="内存大小 (MB)", example=2048)
    vcpu: int = Field(..., description="虚拟 CPU 数量", example=2)
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class VMDetailResponse(VMResponse):
    """虚拟机详情响应模型"""

    uuid: str = Field(..., description="虚拟机 UUID", example="123e4567-e89b-12d3-a456-426614174000")
    disk_path: str = Field(..., description="磁盘镜像路径", example="/var/lib/libvirt/images/ubuntu.qcow2")
    disk_format: str = Field(..., description="磁盘格式", example="qcow2")
    disk_size: Optional[int] = Field(..., description="磁盘大小 (MB)", example=20480)
    iso_path: Optional[str] = Field(..., description="ISO 镜像路径", example="/var/lib/libvirt/isos/ubuntu-22.04.iso")
    network: str = Field(..., description="网络名称", example="default")
    graphics: bool = Field(..., description="是否启用图形显示", example=False)
    graphics_port: Optional[int] = Field(..., description="图形显示端口", example=5900)
    description: Optional[str] = Field(..., description="虚拟机描述", example="Ubuntu 22.04 Server")
    xml: str = Field(..., description="虚拟机 XML 定义")

    # 运行时信息
    cpu_usage: Optional[float] = Field(None, description="CPU 使用率 (%)", ge=0.0, le=100.0)
    memory_usage: Optional[int] = Field(None, description="内存使用量 (MB)", ge=0)
    disk_usage: Optional[int] = Field(None, description="磁盘使用量 (MB)", ge=0)
    ip_addresses: Optional[List[str]] = Field(None, description="IP 地址列表")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class VMListResponse(BaseModel):
    """虚拟机列表响应模型"""

    vms: List[VMResponse] = Field(..., description="虚拟机列表")
    total: int = Field(..., description="总数", example=10)
    page: int = Field(..., description="当前页码", example=1)
    page_size: int = Field(..., description="每页数量", example=20)
    total_pages: int = Field(..., description="总页数", example=1)


class VMStats(BaseModel):
    """虚拟机统计信息"""

    cpu_usage: float = Field(..., description="CPU 使用率 (%)", ge=0.0, le=100.0)
    memory_usage: int = Field(..., description="内存使用量 (MB)", ge=0)
    memory_total: int = Field(..., description="内存总量 (MB)", ge=0)
    disk_usage: int = Field(..., description="磁盘使用量 (MB)", ge=0)
    disk_total: int = Field(..., description="磁盘总量 (MB)", ge=0)
    network_rx_bytes: int = Field(..., description="网络接收字节数", ge=0)
    network_tx_bytes: int = Field(..., description="网络发送字节数", ge=0)
    uptime: int = Field(..., description="运行时间 (秒)", ge=0)
    timestamp: datetime = Field(..., description="统计时间戳")


# 状态转换映射
VM_STATUS_MAPPING = {
    0: VMStatus.NOSTATE,
    1: VMStatus.RUNNING,
    2: VMStatus.BLOCKED,
    3: VMStatus.PAUSED,
    4: VMStatus.SHUTDOWN,
    5: VMStatus.SHUTOFF,
    6: VMStatus.CRASHED,
    7: VMStatus.PMSUSPENDED,
}


def libvirt_status_to_vm_status(libvirt_status: int) -> VMStatus:
    """
    将 libvirt 状态码转换为 VMStatus 枚举

    Args:
        libvirt_status: libvirt 状态码

    Returns:
        VMStatus: 对应的状态枚举
    """
    return VM_STATUS_MAPPING.get(libvirt_status, VMStatus.NOSTATE)


def vm_status_to_libvirt_status(vm_status: VMStatus) -> Optional[int]:
    """
    将 VMStatus 枚举转换为 libvirt 状态码

    Args:
        vm_status: VMStatus 枚举

    Returns:
        Optional[int]: 对应的 libvirt 状态码，如果未找到则返回 None
    """
    reverse_mapping = {v: k for k, v in VM_STATUS_MAPPING.items()}
    return reverse_mapping.get(vm_status)