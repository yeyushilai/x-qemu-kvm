"""
虚拟机模型单元测试
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.models.vm import (
    VMCreateRequest,
    VMUpdateRequest,
    VMResponse,
    VMDetailResponse,
    VMStatus,
    libvirt_status_to_vm_status,
    vm_status_to_libvirt_status,
)


class TestVMCreateRequest:
    """测试 VMCreateRequest 模型"""

    def test_valid_creation(self):
        """测试有效创建"""
        data = {
            "name": "test-vm",
            "memory": 2048,
            "vcpu": 2,
            "disk_path": "/var/lib/libvirt/images/test.qcow2",
            "disk_format": "qcow2",
            "disk_size": 20480,
            "iso_path": "/var/lib/libvirt/isos/test.iso",
            "network": "default",
            "graphics": True,
            "graphics_port": 5900,
            "description": "Test VM",
        }
        vm = VMCreateRequest(**data)
        assert vm.name == "test-vm"
        assert vm.memory == 2048
        assert vm.vcpu == 2
        assert vm.disk_path == "/var/lib/libvirt/images/test.qcow2"
        assert vm.disk_format == "qcow2"
        assert vm.disk_size == 20480
        assert vm.iso_path == "/var/lib/libvirt/isos/test.iso"
        assert vm.network == "default"
        assert vm.graphics is True
        assert vm.graphics_port == 5900
        assert vm.description == "Test VM"

    def test_minimal_creation(self):
        """测试最小化创建"""
        data = {
            "name": "minimal-vm",
            "memory": 1024,
            "vcpu": 1,
            "disk_path": "/var/lib/libvirt/images/minimal.qcow2",
        }
        vm = VMCreateRequest(**data)
        assert vm.name == "minimal-vm"
        assert vm.memory == 1024
        assert vm.vcpu == 1
        assert vm.disk_path == "/var/lib/libvirt/images/minimal.qcow2"
        assert vm.disk_format == "qcow2"  # 默认值
        assert vm.disk_size is None
        assert vm.iso_path is None
        assert vm.network == "default"  # 默认值
        assert vm.graphics is False  # 默认值
        assert vm.graphics_port is None
        assert vm.description is None

    def test_invalid_name(self):
        """测试无效名称"""
        data = {
            "name": "invalid name!",  # 包含空格和特殊字符
            "memory": 1024,
            "vcpu": 1,
            "disk_path": "/var/lib/libvirt/images/test.qcow2",
        }
        with pytest.raises(ValidationError):
            VMCreateRequest(**data)

    def test_invalid_memory(self):
        """测试无效内存"""
        data = {
            "name": "test-vm",
            "memory": 0,  # 必须大于0
            "vcpu": 1,
            "disk_path": "/var/lib/libvirt/images/test.qcow2",
        }
        with pytest.raises(ValidationError):
            VMCreateRequest(**data)

    def test_invalid_vcpu(self):
        """测试无效CPU"""
        data = {
            "name": "test-vm",
            "memory": 1024,
            "vcpu": 0,  # 必须大于0
            "disk_path": "/var/lib/libvirt/images/test.qcow2",
        }
        with pytest.raises(ValidationError):
            VMCreateRequest(**data)

    def test_memory_validation_power_of_two(self):
        """测试内存2的幂次方验证"""
        data = {
            "name": "test-vm",
            "memory": 3000,  # 不是2的幂
            "vcpu": 1,
            "disk_path": "/var/lib/libvirt/images/test.qcow2",
        }
        vm = VMCreateRequest(**data)
        # 应该向上取整到最近的2的幂
        assert vm.memory == 4096  # 2^12


class TestVMUpdateRequest:
    """测试 VMUpdateRequest 模型"""

    def test_valid_update(self):
        """测试有效更新"""
        data = {
            "memory": 4096,
            "vcpu": 4,
            "description": "Updated description",
        }
        update = VMUpdateRequest(**data)
        assert update.memory == 4096
        assert update.vcpu == 4
        assert update.description == "Updated description"

    def test_partial_update(self):
        """测试部分更新"""
        data = {
            "memory": 4096,
        }
        update = VMUpdateRequest(**data)
        assert update.memory == 4096
        assert update.vcpu is None
        assert update.description is None

    def test_empty_update(self):
        """测试空更新"""
        data = {}
        update = VMUpdateRequest(**data)
        assert update.memory is None
        assert update.vcpu is None
        assert update.description is None


class TestVMResponse:
    """测试 VMResponse 模型"""

    def test_valid_response(self):
        """测试有效响应"""
        data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "test-vm",
            "status": VMStatus.RUNNING,
            "memory": 2048,
            "vcpu": 2,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        vm = VMResponse(**data)
        assert vm.id == "123e4567-e89b-12d3-a456-426614174000"
        assert vm.name == "test-vm"
        assert vm.status == VMStatus.RUNNING
        assert vm.memory == 2048
        assert vm.vcpu == 2


class TestVMStatus:
    """测试 VMStatus 枚举和转换函数"""

    def test_status_mapping(self):
        """测试状态映射"""
        # libvirt 状态码到 VMStatus
        assert libvirt_status_to_vm_status(0) == VMStatus.NOSTATE
        assert libvirt_status_to_vm_status(1) == VMStatus.RUNNING
        assert libvirt_status_to_vm_status(2) == VMStatus.BLOCKED
        assert libvirt_status_to_vm_status(3) == VMStatus.PAUSED
        assert libvirt_status_to_vm_status(4) == VMStatus.SHUTDOWN
        assert libvirt_status_to_vm_status(5) == VMStatus.SHUTOFF
        assert libvirt_status_to_vm_status(6) == VMStatus.CRASHED
        assert libvirt_status_to_vm_status(7) == VMStatus.PMSUSPENDED

        # 未知状态码
        assert libvirt_status_to_vm_status(999) == VMStatus.NOSTATE

    def test_reverse_status_mapping(self):
        """测试反向状态映射"""
        # VMStatus 到 libvirt 状态码
        assert vm_status_to_libvirt_status(VMStatus.NOSTATE) == 0
        assert vm_status_to_libvirt_status(VMStatus.RUNNING) == 1
        assert vm_status_to_libvirt_status(VMStatus.BLOCKED) == 2
        assert vm_status_to_libvirt_status(VMStatus.PAUSED) == 3
        assert vm_status_to_libvirt_status(VMStatus.SHUTDOWN) == 4
        assert vm_status_to_libvirt_status(VMStatus.SHUTOFF) == 5
        assert vm_status_to_libvirt_status(VMStatus.CRASHED) == 6
        assert vm_status_to_libvirt_status(VMStatus.PMSUSPENDED) == 7


class TestVMDetailResponse:
    """测试 VMDetailResponse 模型"""

    def test_valid_detail_response(self):
        """测试有效详情响应"""
        base_data = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "test-vm",
            "status": VMStatus.RUNNING,
            "memory": 2048,
            "vcpu": 2,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        detail_data = {
            **base_data,
            "uuid": "123e4567-e89b-12d3-a456-426614174000",
            "disk_path": "/var/lib/libvirt/images/test.qcow2",
            "disk_format": "qcow2",
            "disk_size": 20480,
            "iso_path": "/var/lib/libvirt/isos/test.iso",
            "network": "default",
            "graphics": True,
            "graphics_port": 5900,
            "description": "Test VM",
            "xml": "<domain>...</domain>",
            "cpu_usage": 25.5,
            "memory_usage": 1024,
            "disk_usage": 10240,
            "ip_addresses": ["192.168.1.100"],
        }

        vm = VMDetailResponse(**detail_data)
        assert vm.uuid == "123e4567-e89b-12d3-a456-426614174000"
        assert vm.disk_path == "/var/lib/libvirt/images/test.qcow2"
        assert vm.disk_format == "qcow2"
        assert vm.disk_size == 20480
        assert vm.iso_path == "/var/lib/libvirt/isos/test.iso"
        assert vm.network == "default"
        assert vm.graphics is True
        assert vm.graphics_port == 5900
        assert vm.description == "Test VM"
        assert vm.xml == "<domain>...</domain>"
        assert vm.cpu_usage == 25.5
        assert vm.memory_usage == 1024
        assert vm.disk_usage == 10240
        assert vm.ip_addresses == ["192.168.1.100"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])