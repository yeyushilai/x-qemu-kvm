"""
虚拟机服务层

该模块提供虚拟机管理的核心业务逻辑，
包括虚拟机的创建、删除、启动、停止等操作。
"""

import logging
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional, Dict, Any
from xml.dom import minidom

from src.core.hypervisor import hypervisor_context
from src.core.exceptions import (
    VMNotFoundError,
    VMAlreadyExistsError,
    VMStateError,
    VMOperationError,
    XMLValidationError,
    wrap_libvirt_error,
)
from src.models.vm import (
    VMCreateRequest,
    VMUpdateRequest,
    VMResponse,
    VMDetailResponse,
    VMListResponse,
    VMStatus,
    libvirt_status_to_vm_status,
)

logger = logging.getLogger(__name__)


class VMService:
    """虚拟机服务"""

    def __init__(self, uri: str = "qemu:///system"):
        """
        初始化虚拟机服务

        Args:
            uri: libvirt 连接 URI
        """
        self.uri = uri

    @wrap_libvirt_error
    def list_vms(
        self,
        active_only: bool = False,
        inactive_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> VMListResponse:
        """
        列出所有虚拟机

        Args:
            active_only: 是否只列出活跃的虚拟机
            inactive_only: 是否只列出非活跃的虚拟机
            page: 页码
            page_size: 每页数量

        Returns:
            VMListResponse: 虚拟机列表响应
        """
        with hypervisor_context(self.uri) as hv:
            # 设置 libvirt 标志
            flags = 0
            if active_only:
                flags |= 1  # VIR_CONNECT_LIST_DOMAINS_ACTIVE
            if inactive_only:
                flags |= 2  # VIR_CONNECT_LIST_DOMAINS_INACTIVE

            domains = hv.list_domains(flags)
            total = len(domains)

            # 分页
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paged_domains = domains[start_idx:end_idx]

            # 转换为响应模型
            vm_responses = []
            for domain in paged_domains:
                try:
                    vm_info = self._domain_to_vm_response(domain)
                    vm_responses.append(vm_info)
                except Exception as e:
                    logger.warning(f"获取虚拟机信息失败: {e}")
                    continue

            total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1

            return VMListResponse(
                vms=vm_responses,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            )

    @wrap_libvirt_error
    def get_vm(self, vm_id: str, by_uuid: bool = False) -> VMDetailResponse:
        """
        获取虚拟机详情

        Args:
            vm_id: 虚拟机 ID（名称或 UUID）
            by_uuid: 是否按 UUID 查找

        Returns:
            VMDetailResponse: 虚拟机详情响应

        Raises:
            VMNotFoundError: 虚拟机未找到
        """
        with hypervisor_context(self.uri) as hv:
            try:
                if by_uuid:
                    domain = hv.get_domain_by_uuid(vm_id)
                else:
                    domain = hv.get_domain_by_name(vm_id)
            except Exception as e:
                raise VMNotFoundError(f"虚拟机未找到: {vm_id}") from e

            return self._domain_to_vm_detail_response(domain)

    @wrap_libvirt_error
    def create_vm(self, vm_data: VMCreateRequest) -> VMDetailResponse:
        """
        创建虚拟机

        Args:
            vm_data: 虚拟机创建请求数据

        Returns:
            VMDetailResponse: 创建的虚拟机详情

        Raises:
            VMAlreadyExistsError: 虚拟机已存在
            XMLValidationError: XML 定义验证失败
        """
        # 检查虚拟机是否已存在
        try:
            existing_vm = self.get_vm(vm_data.name)
            raise VMAlreadyExistsError(f"虚拟机已存在: {vm_data.name}")
        except VMNotFoundError:
            # 虚拟机不存在，继续创建
            pass

        # 生成 XML 定义
        xml_str = self._generate_domain_xml(vm_data)

        # 验证 XML
        if not self._validate_xml(xml_str):
            raise XMLValidationError("生成的 XML 定义无效")

        with hypervisor_context(self.uri) as hv:
            try:
                # 定义虚拟机
                domain = hv.define_domain(xml_str)

                # 获取虚拟机详情
                vm_detail = self._domain_to_vm_detail_response(domain)

                logger.info(f"虚拟机创建成功: {vm_data.name} (ID: {vm_detail.id})")
                return vm_detail

            except Exception as e:
                logger.error(f"创建虚拟机失败: {e}")
                raise VMOperationError(f"创建虚拟机失败: {e}") from e

    @wrap_libvirt_error
    def start_vm(self, vm_id: str, by_uuid: bool = False) -> VMResponse:
        """
        启动虚拟机

        Args:
            vm_id: 虚拟机 ID（名称或 UUID）
            by_uuid: 是否按 UUID 查找

        Returns:
            VMResponse: 虚拟机响应

        Raises:
            VMNotFoundError: 虚拟机未找到
            VMStateError: 虚拟机状态不允许启动
        """
        with hypervisor_context(self.uri) as hv:
            try:
                if by_uuid:
                    domain = hv.get_domain_by_uuid(vm_id)
                else:
                    domain = hv.get_domain_by_name(vm_id)
            except Exception as e:
                raise VMNotFoundError(f"虚拟机未找到: {vm_id}") from e

            # 检查状态
            state, _ = domain.state()
            if state == 1:  # VIR_DOMAIN_RUNNING
                raise VMStateError(f"虚拟机已在运行中: {vm_id}")
            elif state == 3:  # VIR_DOMAIN_PAUSED
                # 恢复暂停的虚拟机
                domain.resume()
            else:
                # 启动虚拟机
                domain.create()

            # 获取更新后的信息
            vm_response = self._domain_to_vm_response(domain)
            logger.info(f"虚拟机启动成功: {vm_id}")
            return vm_response

    @wrap_libvirt_error
    def stop_vm(self, vm_id: str, force: bool = False, by_uuid: bool = False) -> VMResponse:
        """
        停止虚拟机

        Args:
            vm_id: 虚拟机 ID（名称或 UUID）
            force: 是否强制停止
            by_uuid: 是否按 UUID 查找

        Returns:
            VMResponse: 虚拟机响应

        Raises:
            VMNotFoundError: 虚拟机未找到
            VMStateError: 虚拟机状态不允许停止
        """
        with hypervisor_context(self.uri) as hv:
            try:
                if by_uuid:
                    domain = hv.get_domain_by_uuid(vm_id)
                else:
                    domain = hv.get_domain_by_name(vm_id)
            except Exception as e:
                raise VMNotFoundError(f"虚拟机未找到: {vm_id}") from e

            # 检查状态
            state, _ = domain.state()
            if state == 5:  # VIR_DOMAIN_SHUTOFF
                raise VMStateError(f"虚拟机已关闭: {vm_id}")

            if force:
                # 强制停止
                domain.destroy()
            else:
                # 优雅关机
                try:
                    domain.shutdown()
                except Exception as e:
                    logger.warning(f"优雅关机失败，尝试强制停止: {e}")
                    domain.destroy()

            # 获取更新后的信息
            vm_response = self._domain_to_vm_response(domain)
            logger.info(f"虚拟机停止成功: {vm_id} (强制: {force})")
            return vm_response

    @wrap_libvirt_error
    def restart_vm(self, vm_id: str, force: bool = False, by_uuid: bool = False) -> VMResponse:
        """
        重启虚拟机

        Args:
            vm_id: 虚拟机 ID（名称或 UUID）
            force: 是否强制重启
            by_uuid: 是否按 UUID 查找

        Returns:
            VMResponse: 虚拟机响应

        Raises:
            VMNotFoundError: 虚拟机未找到
        """
        # 先停止
        self.stop_vm(vm_id, force=force, by_uuid=by_uuid)

        # 再启动
        return self.start_vm(vm_id, by_uuid=by_uuid)

    @wrap_libvirt_error
    def pause_vm(self, vm_id: str, by_uuid: bool = False) -> VMResponse:
        """
        暂停虚拟机

        Args:
            vm_id: 虚拟机 ID（名称或 UUID）
            by_uuid: 是否按 UUID 查找

        Returns:
            VMResponse: 虚拟机响应

        Raises:
            VMNotFoundError: 虚拟机未找到
            VMStateError: 虚拟机状态不允许暂停
        """
        with hypervisor_context(self.uri) as hv:
            try:
                if by_uuid:
                    domain = hv.get_domain_by_uuid(vm_id)
                else:
                    domain = hv.get_domain_by_name(vm_id)
            except Exception as e:
                raise VMNotFoundError(f"虚拟机未找到: {vm_id}") from e

            # 检查状态
            state, _ = domain.state()
            if state != 1:  # 不是运行状态
                raise VMStateError(f"虚拟机不在运行状态，无法暂停: {vm_id}")

            # 暂停虚拟机
            domain.suspend()

            # 获取更新后的信息
            vm_response = self._domain_to_vm_response(domain)
            logger.info(f"虚拟机暂停成功: {vm_id}")
            return vm_response

    @wrap_libvirt_error
    def resume_vm(self, vm_id: str, by_uuid: bool = False) -> VMResponse:
        """
        恢复虚拟机

        Args:
            vm_id: 虚拟机 ID（名称或 UUID）
            by_uuid: 是否按 UUID 查找

        Returns:
            VMResponse: 虚拟机响应

        Raises:
            VMNotFoundError: 虚拟机未找到
            VMStateError: 虚拟机状态不允许恢复
        """
        with hypervisor_context(self.uri) as hv:
            try:
                if by_uuid:
                    domain = hv.get_domain_by_uuid(vm_id)
                else:
                    domain = hv.get_domain_by_name(vm_id)
            except Exception as e:
                raise VMNotFoundError(f"虚拟机未找到: {vm_id}") from e

            # 检查状态
            state, _ = domain.state()
            if state != 3:  # 不是暂停状态
                raise VMStateError(f"虚拟机不在暂停状态，无法恢复: {vm_id}")

            # 恢复虚拟机
            domain.resume()

            # 获取更新后的信息
            vm_response = self._domain_to_vm_response(domain)
            logger.info(f"虚拟机恢复成功: {vm_id}")
            return vm_response

    @wrap_libvirt_error
    def delete_vm(self, vm_id: str, delete_disk: bool = False, by_uuid: bool = False) -> None:
        """
        删除虚拟机

        Args:
            vm_id: 虚拟机 ID（名称或 UUID）
            delete_disk: 是否删除磁盘文件
            by_uuid: 是否按 UUID 查找

        Raises:
            VMNotFoundError: 虚拟机未找到
        """
        with hypervisor_context(self.uri) as hv:
            try:
                if by_uuid:
                    domain = hv.get_domain_by_uuid(vm_id)
                else:
                    domain = hv.get_domain_by_name(vm_id)
            except Exception as e:
                raise VMNotFoundError(f"虚拟机未找到: {vm_id}") from e

            # 如果虚拟机正在运行，先停止
            state, _ = domain.state()
            if state == 1:  # VIR_DOMAIN_RUNNING
                try:
                    domain.destroy()
                except Exception as e:
                    logger.warning(f"停止运行中的虚拟机失败: {e}")

            # 获取磁盘路径（用于删除磁盘文件）
            disk_path = None
            if delete_disk:
                try:
                    xml_str = domain.XMLDesc(0)
                    disk_path = self._extract_disk_path(xml_str)
                except Exception as e:
                    logger.warning(f"获取磁盘路径失败: {e}")

            # 取消定义虚拟机
            domain.undefine()

            # 删除磁盘文件
            if delete_disk and disk_path:
                try:
                    import os
                    if os.path.exists(disk_path):
                        os.remove(disk_path)
                        logger.info(f"已删除磁盘文件: {disk_path}")
                except Exception as e:
                    logger.warning(f"删除磁盘文件失败: {e}")

            logger.info(f"虚拟机删除成功: {vm_id} (删除磁盘: {delete_disk})")

    @wrap_libvirt_error
    def update_vm(self, vm_id: str, vm_data: VMUpdateRequest, by_uuid: bool = False) -> VMDetailResponse:
        """
        更新虚拟机配置

        Args:
            vm_id: 虚拟机 ID（名称或 UUID）
            vm_data: 虚拟机更新请求数据
            by_uuid: 是否按 UUID 查找

        Returns:
            VMDetailResponse: 更新后的虚拟机详情

        Raises:
            VMNotFoundError: 虚拟机未找到
            VMOperationError: 更新失败
        """
        with hypervisor_context(self.uri) as hv:
            try:
                if by_uuid:
                    domain = hv.get_domain_by_uuid(vm_id)
                else:
                    domain = hv.get_domain_by_name(vm_id)
            except Exception as e:
                raise VMNotFoundError(f"虚拟机未找到: {vm_id}") from e

            # 获取当前 XML
            current_xml = domain.XMLDesc(0)
            updated_xml = self._update_domain_xml(current_xml, vm_data)

            # 重新定义虚拟机
            try:
                domain = hv.define_domain(updated_xml)
            except Exception as e:
                raise VMOperationError(f"更新虚拟机配置失败: {e}") from e

            # 获取更新后的详情
            vm_detail = self._domain_to_vm_detail_response(domain)
            logger.info(f"虚拟机更新成功: {vm_id}")
            return vm_detail

    def _domain_to_vm_response(self, domain) -> VMResponse:
        """
        将 libvirt 域对象转换为 VMResponse

        Args:
            domain: libvirt.virDomain 对象

        Returns:
            VMResponse: 虚拟机响应
        """
        # 获取基本信息
        domain_id = domain.ID()
        name = domain.name()
        uuid_str = domain.UUIDString()

        # 获取状态
        state, _ = domain.state()
        status = libvirt_status_to_vm_status(state)

        # 获取创建时间
        info = domain.info()
        # info[4] 是运行时间（秒），我们用它估算创建时间
        uptime = info[4]
        created_at = datetime.now() if uptime == 0 else datetime.fromtimestamp(
            datetime.now().timestamp() - uptime
        )

        # 获取配置信息（需要解析 XML）
        memory = 0
        vcpu = 0
        try:
            xml_str = domain.XMLDesc(0)
            root = ET.fromstring(xml_str)

            # 提取内存和 CPU
            memory_elem = root.find("./memory")
            if memory_elem is not None:
                memory = int(memory_elem.text) // 1024  # 转换为 MB

            vcpu_elem = root.find("./vcpu")
            if vcpu_elem is not None:
                vcpu = int(vcpu_elem.text)
        except Exception as e:
            logger.warning(f"解析虚拟机 XML 失败: {e}")

        return VMResponse(
            id=uuid_str,
            name=name,
            status=status,
            memory=memory,
            vcpu=vcpu,
            created_at=created_at,
            updated_at=datetime.now(),
        )

    def _domain_to_vm_detail_response(self, domain) -> VMDetailResponse:
        """
        将 libvirt 域对象转换为 VMDetailResponse

        Args:
            domain: libvirt.virDomain 对象

        Returns:
            VMDetailResponse: 虚拟机详情响应
        """
        # 获取基础响应
        vm_response = self._domain_to_vm_response(domain)

        # 获取 XML 定义
        xml_str = domain.XMLDesc(0)
        root = ET.fromstring(xml_str)

        # 提取详细信息
        disk_path = None
        disk_format = None
        disk_size = None
        iso_path = None
        network = "default"
        graphics = False
        graphics_port = None
        description = None

        try:
            # 磁盘信息
            disk_elem = root.find("./devices/disk[@device='disk']/source")
            if disk_elem is not None:
                disk_path = disk_elem.get("file")
                # 从文件路径推断格式
                if disk_path and disk_path.endswith(".qcow2"):
                    disk_format = "qcow2"
                elif disk_path and disk_path.endswith(".raw"):
                    disk_format = "raw"

            # ISO 信息
            cdrom_elem = root.find("./devices/disk[@device='cdrom']/source")
            if cdrom_elem is not None:
                iso_path = cdrom_elem.get("file")

            # 网络信息
            interface_elem = root.find("./devices/interface/source")
            if interface_elem is not None:
                network = interface_elem.get("network", "default")

            # 图形显示信息
            graphics_elem = root.find("./devices/graphics")
            if graphics_elem is not None:
                graphics = True
                port_attr = graphics_elem.get("port")
                if port_attr:
                    graphics_port = int(port_attr)

            # 描述信息
            description_elem = root.find("./description")
            if description_elem is not None:
                description = description_elem.text

        except Exception as e:
            logger.warning(f"提取虚拟机详细信息失败: {e}")

        # 获取运行时统计信息
        cpu_usage = None
        memory_usage = None
        disk_usage = None
        ip_addresses = []

        try:
            # 这里可以添加获取运行时统计信息的逻辑
            # 例如：domain.getCPUStats(), domain.memoryStats(), 等
            pass
        except Exception as e:
            logger.debug(f"获取运行时统计信息失败: {e}")

        return VMDetailResponse(
            **vm_response.dict(),
            uuid=domain.UUIDString(),
            disk_path=disk_path or "",
            disk_format=disk_format or "",
            disk_size=disk_size,
            iso_path=iso_path,
            network=network,
            graphics=graphics,
            graphics_port=graphics_port,
            description=description,
            xml=xml_str,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            ip_addresses=ip_addresses,
        )

    def _generate_domain_xml(self, vm_data: VMCreateRequest) -> str:
        """
        生成虚拟机 XML 定义

        Args:
            vm_data: 虚拟机创建请求数据

        Returns:
            str: XML 定义字符串
        """
        # 这里实现 XML 生成逻辑
        # 由于时间关系，这里返回一个简单的模板
        # 实际项目中应该实现完整的 XML 生成器

        xml_template = f"""<domain type='kvm'>
  <name>{vm_data.name}</name>
  <memory unit='MiB'>{vm_data.memory}</memory>
  <vcpu>{vm_data.vcpu}</vcpu>
  <os>
    <type arch='x86_64' machine='pc-q35-7.2'>hvm</type>
    <boot dev='hd'/>
    {"<boot dev='cdrom'/>" if vm_data.iso_path else ""}
  </os>
  <devices>
    <disk type='file' device='disk'>
      <driver name='qemu' type='{vm_data.disk_format}'/>
      <source file='{vm_data.disk_path}'/>
      <target dev='vda' bus='virtio'/>
    </disk>
    {"<disk type='file' device='cdrom'>" + f"""
      <driver name='qemu' type='raw'/>
      <source file='{vm_data.iso_path}'/>
      <target dev='sda' bus='sata'/>
      <readonly/>
    </disk>""" if vm_data.iso_path else ""}
    <interface type='network'>
      <source network='{vm_data.network}'/>
      <model type='virtio'/>
    </interface>
    {"<graphics type='vnc' port='-1' autoport='yes' listen='0.0.0.0'/>" if vm_data.graphics else ""}
    <video>
      <model type='virtio'/>
    </video>
    <input type='tablet' bus='usb'/>
    <input type='keyboard' bus='usb'/>
  </devices>
</domain>"""

        return xml_template

    def _validate_xml(self, xml_str: str) -> bool:
        """
        验证 XML 定义是否有效

        Args:
            xml_str: XML 字符串

        Returns:
            bool: 是否有效
        """
        try:
            ET.fromstring(xml_str)
            return True
        except ET.ParseError as e:
            logger.error(f"XML 解析失败: {e}")
            return False

    def _extract_disk_path(self, xml_str: str) -> Optional[str]:
        """
        从 XML 中提取磁盘路径

        Args:
            xml_str: XML 字符串

        Returns:
            Optional[str]: 磁盘路径，如果未找到则返回 None
        """
        try:
            root = ET.fromstring(xml_str)
            disk_elem = root.find("./devices/disk[@device='disk']/source")
            if disk_elem is not None:
                return disk_elem.get("file")
        except Exception as e:
            logger.warning(f"提取磁盘路径失败: {e}")
        return None

    def _update_domain_xml(self, current_xml: str, vm_data: VMUpdateRequest) -> str:
        """
        更新域 XML 定义

        Args:
            current_xml: 当前 XML 定义
            vm_data: 更新数据

        Returns:
            str: 更新后的 XML 定义
        """
        try:
            root = ET.fromstring(current_xml)

            # 更新内存
            if vm_data.memory is not None:
                memory_elem = root.find("./memory")
                if memory_elem is not None:
                    memory_elem.text = str(vm_data.memory * 1024)  # 转换为 KB
                    memory_elem.set("unit", "KiB")

            # 更新 CPU
            if vm_data.vcpu is not None:
                vcpu_elem = root.find("./vcpu")
                if vcpu_elem is not None:
                    vcpu_elem.text = str(vm_data.vcpu)

            # 更新描述
            if vm_data.description is not None:
                description_elem = root.find("./description")
                if description_elem is None:
                    description_elem = ET.SubElement(root, "description")
                description_elem.text = vm_data.description

            # 将 XML 转换回字符串
            xml_str = ET.tostring(root, encoding="unicode")
            # 美化输出
            xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")

            return xml_str

        except Exception as e:
            logger.error(f"更新 XML 定义失败: {e}")
            raise XMLValidationError(f"更新 XML 定义失败: {e}") from e