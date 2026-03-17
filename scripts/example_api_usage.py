"""
示例：如何使用 x-qemu-kvm API

这个示例展示了如何通过 Python 代码使用 x-qemu-kvm 的 API。
"""

import sys
import time
import json
import requests
from typing import Dict, Any

# API 基础 URL
BASE_URL = "http://localhost:8000/api/v1"


def print_response(response: requests.Response):
    """打印响应信息"""
    print(f"Status Code: {response.status_code}")
    if response.headers.get("Content-Type", "").startswith("application/json"):
        try:
            print("Response Body:")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(f"Response Text: {response.text}")
    else:
        print(f"Response Text: {response.text}")
    print("-" * 50)


def list_virtual_machines():
    """列出所有虚拟机"""
    print("列出所有虚拟机...")
    response = requests.get(f"{BASE_URL}/vms")
    print_response(response)
    return response.json() if response.status_code == 200 else None


def create_virtual_machine():
    """创建新虚拟机"""
    print("创建新虚拟机...")

    vm_data = {
        "name": "example-vm",
        "memory": 2048,
        "vcpu": 2,
        "disk_path": "/var/lib/libvirt/images/example.qcow2",
        "disk_format": "qcow2",
        "disk_size": 20480,
        "iso_path": "/var/lib/libvirt/isos/ubuntu-22.04.iso",
        "network": "default",
        "graphics": False,
        "description": "示例虚拟机，用于演示 API 使用",
    }

    response = requests.post(
        f"{BASE_URL}/vms",
        json=vm_data,
        headers={"Content-Type": "application/json"}
    )
    print_response(response)
    return response.json() if response.status_code == 201 else None


def get_virtual_machine(vm_id: str):
    """获取虚拟机详情"""
    print(f"获取虚拟机详情: {vm_id}...")
    response = requests.get(f"{BASE_URL}/vms/{vm_id}")
    print_response(response)
    return response.json() if response.status_code == 200 else None


def start_virtual_machine(vm_id: str):
    """启动虚拟机"""
    print(f"启动虚拟机: {vm_id}...")
    response = requests.post(f"{BASE_URL}/vms/{vm_id}/start")
    print_response(response)
    return response.json() if response.status_code == 200 else None


def stop_virtual_machine(vm_id: str):
    """停止虚拟机"""
    print(f"停止虚拟机: {vm_id}...")
    response = requests.post(f"{BASE_URL}/vms/{vm_id}/stop")
    print_response(response)
    return response.json() if response.status_code == 200 else None


def delete_virtual_machine(vm_id: str, delete_disk: bool = False):
    """删除虚拟机"""
    print(f"删除虚拟机: {vm_id} (删除磁盘: {delete_disk})...")
    response = requests.delete(
        f"{BASE_URL}/vms/{vm_id}",
        params={"delete_disk": delete_disk}
    )
    print_response(response)
    return response.status_code == 204


def main():
    """主函数：演示完整的虚拟机生命周期"""
    print("=" * 60)
    print("x-qemu-kvm API 使用示例")
    print("=" * 60)

    # 步骤1: 列出虚拟机
    print("\n1. 列出当前所有虚拟机")
    vms = list_virtual_machines()

    # 步骤2: 创建虚拟机
    print("\n2. 创建新虚拟机")
    created_vm = create_virtual_machine()

    if created_vm:
        vm_id = created_vm.get("name")  # 或使用 id/uuid
        vm_name = created_vm.get("name")

        # 等待一会儿让虚拟机定义完成
        time.sleep(2)

        # 步骤3: 获取虚拟机详情
        print("\n3. 获取虚拟机详情")
        get_virtual_machine(vm_name)

        # 步骤4: 启动虚拟机
        print("\n4. 启动虚拟机")
        start_virtual_machine(vm_name)

        # 等待虚拟机启动
        time.sleep(5)

        # 步骤5: 再次获取详情（查看状态变化）
        print("\n5. 获取启动后的虚拟机详情")
        get_virtual_machine(vm_name)

        # 步骤6: 停止虚拟机
        print("\n6. 停止虚拟机")
        stop_virtual_machine(vm_name)

        # 等待虚拟机停止
        time.sleep(3)

        # 步骤7: 删除虚拟机（不删除磁盘）
        print("\n7. 删除虚拟机")
        delete_virtual_machine(vm_name, delete_disk=False)

        print("\n✅ 虚拟机生命周期演示完成！")
    else:
        print("\n❌ 创建虚拟机失败，跳过后续步骤")

    # 最终状态
    print("\n最终状态:")
    list_virtual_machines()


def health_check():
    """健康检查"""
    print("执行健康检查...")
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ API 服务运行正常")
            print(f"服务信息: {response.json()}")
            return True
        else:
            print(f"❌ API 服务异常: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到 API 服务，请确保服务已启动")
        print("启动命令: uv run uvicorn src.api.main:app --reload")
        return False
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
        return False


if __name__ == "__main__":
    # 检查 API 服务是否可用
    if not health_check():
        sys.exit(1)

    # 运行示例
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n示例被用户中断")
    except Exception as e:
        print(f"\n❌ 示例执行失败: {e}")
        import traceback
        traceback.print_exc()