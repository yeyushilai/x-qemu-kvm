"""
Hypervisor 连接管理器

该模块负责管理与 libvirt hypervisor 的连接，
提供连接池、上下文管理等功能。
"""

import logging
import sys
from contextlib import contextmanager
from typing import Optional, Dict, Any, Generator

from .exceptions import (
    HypervisorConnectionError,
    HypervisorNotSupportedError,
    wrap_libvirt_error,
)

logger = logging.getLogger(__name__)

# 尝试导入 libvirt，如果失败则设置标志
try:
    import libvirt
    LIBVIRT_AVAILABLE = True
except ImportError:
    LIBVIRT_AVAILABLE = False
    libvirt = None


class HypervisorManager:
    """
    Hypervisor 连接管理器

    提供统一的接口来管理 libvirt 连接，支持连接池和自动重连。
    """

    def __init__(self, uri: str = "qemu:///system"):
        """
        初始化 Hypervisor 管理器

        Args:
            uri: libvirt 连接 URI，默认为 qemu:///system
                - qemu:///system: 系统级连接（需要 root 权限）
                - qemu:///session: 用户级连接
                - 其他: 远程连接 (qemu+ssh://, qemu+tcp://, etc.)
        """
        if not LIBVIRT_AVAILABLE:
            raise ImportError("libvirt-python 未安装。请在 Linux 环境下安装 libvirt-python。")

        self.uri = uri
        self._connection = None
        self._connection_info: Dict[str, Any] = {}

    def __enter__(self):
        """上下文管理器入口，自动连接"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出，自动关闭连接"""
        self.disconnect()

    @wrap_libvirt_error
    def connect(self) -> None:
        """
        连接到 hypervisor

        Raises:
            HypervisorConnectionError: 连接失败时抛出
        """
        if self._connection is not None:
            logger.debug("已存在连接，跳过新连接")
            return

        try:
            logger.info(f"正在连接到 hypervisor: {self.uri}")
            self._connection = libvirt.open(self.uri)

            if self._connection is None:
                raise HypervisorConnectionError(f"无法连接到 {self.uri}")

            # 获取连接信息
            self._connection_info = self._get_connection_info()
            logger.info(f"成功连接到 {self._connection_info.get('type', 'unknown')} hypervisor")

        except libvirt.libvirtError as e:
            logger.error(f"连接失败: {e}")
            raise HypervisorConnectionError(f"连接到 {self.uri} 失败: {e}") from e

    @wrap_libvirt_error
    def disconnect(self) -> None:
        """断开连接"""
        if self._connection is not None:
            try:
                self._connection.close()
                logger.info("已断开 hypervisor 连接")
            except libvirt.libvirtError as e:
                logger.warning(f"断开连接时出错: {e}")
            finally:
                self._connection = None
                self._connection_info = {}

    def _get_connection_info(self) -> Dict[str, Any]:
        """
        获取连接信息

        Returns:
            Dict[str, Any]: 包含 hypervisor 信息的字典
        """
        if self._connection is None:
            return {}

        try:
            # 获取 libvirt 版本
            libvirt_version = self._connection.getLibVersion()
            libvirt_version_str = f"{libvirt_version // 1000000}.{(libvirt_version // 1000) % 1000}.{libvirt_version % 1000}"

            # 获取 hypervisor 类型
            hypervisor_type = self._connection.getType()
            hypervisor_type_str = {
                libvirt.VIR_DOMAIN_XEN: "Xen",
                libvirt.VIR_DOMAIN_QEMU: "QEMU/KVM",
                libvirt.VIR_DOMAIN_LXC: "LXC",
                libvirt.VIR_DOMAIN_UML: "UML",
                libvirt.VIR_DOMAIN_OPENVZ: "OpenVZ",
                libvirt.VIR_DOMAIN_TEST: "Test",
                libvirt.VIR_DOMAIN_VMWARE: "VMware",
                libvirt.VIR_DOMAIN_HYPERV: "Hyper-V",
                libvirt.VIR_DOMAIN_VBOX: "VirtualBox",
                libvirt.VIR_DOMAIN_PHYP: "PHYP",
                libvirt.VIR_DOMAIN_PARALLELS: "Parallels",
                libvirt.VIR_DOMAIN_BHYVE: "Bhyve",
            }.get(hypervisor_type, f"Unknown ({hypervisor_type})")

            # 获取主机信息
            hostname = self._connection.getHostname()
            capabilities_xml = self._connection.getCapabilities()
            # 这里可以解析 capabilities XML 获取更多信息

            return {
                "uri": self.uri,
                "libvirt_version": libvirt_version_str,
                "hypervisor_type": hypervisor_type_str,
                "hostname": hostname,
                "capabilities": capabilities_xml,
                "is_alive": self._connection.isAlive() == 1,
                "is_encrypted": self._connection.isEncrypted() == 1,
                "is_secure": self._connection.isSecure() == 1,
            }
        except libvirt.libvirtError as e:
            logger.warning(f"获取连接信息失败: {e}")
            return {}

    @property
    def connection(self):
        """
        获取 libvirt 连接对象

        Returns:
            libvirt.virConnect: libvirt 连接对象

        Raises:
            HypervisorConnectionError: 如果未连接则抛出
        """
        if self._connection is None:
            raise HypervisorConnectionError("未连接到 hypervisor，请先调用 connect()")
        return self._connection

    @property
    def info(self) -> Dict[str, Any]:
        """
        获取连接信息

        Returns:
            Dict[str, Any]: 连接信息字典
        """
        return self._connection_info.copy()

    @wrap_libvirt_error
    def list_domains(self, flags: int = 0) -> list:
        """
        列出所有虚拟机（域）

        Args:
            flags: libvirt 标志位
                - libvirt.VIR_CONNECT_LIST_DOMAINS_ACTIVE: 活跃的虚拟机
                - libvirt.VIR_CONNECT_LIST_DOMAINS_INACTIVE: 非活跃的虚拟机
                - libvirt.VIR_CONNECT_LIST_DOMAINS_PERSISTENT: 持久的虚拟机
                - libvirt.VIR_CONNECT_LIST_DOMAINS_TRANSIENT: 临时的虚拟机
                - libvirt.VIR_CONNECT_LIST_DOMAINS_RUNNING: 运行中的虚拟机
                - libvirt.VIR_CONNECT_LIST_DOMAINS_PAUSED: 暂停的虚拟机
                - libvirt.VIR_CONNECT_LIST_DOMAINS_SHUTOFF: 关闭的虚拟机
                - libvirt.VIR_CONNECT_LIST_DOMAINS_OTHER: 其他状态的虚拟机

        Returns:
            list: 虚拟机对象列表
        """
        return self.connection.listAllDomains(flags)

    @wrap_libvirt_error
    def get_domain_by_name(self, name: str):
        """
        通过名称获取虚拟机

        Args:
            name: 虚拟机名称

        Returns:
            libvirt.virDomain: 虚拟机对象
        """
        return self.connection.lookupByName(name)

    @wrap_libvirt_error
    def get_domain_by_uuid(self, uuid: str):
        """
        通过 UUID 获取虚拟机

        Args:
            uuid: 虚拟机 UUID

        Returns:
            libvirt.virDomain: 虚拟机对象
        """
        return self.connection.lookupByUUIDString(uuid)

    @wrap_libvirt_error
    def define_domain(self, xml: str):
        """
        从 XML 定义虚拟机

        Args:
            xml: 虚拟机 XML 定义

        Returns:
            libvirt.virDomain: 新定义的虚拟机对象
        """
        return self.connection.defineXML(xml)

    @wrap_libvirt_error
    def create_domain(self, xml: str):
        """
        从 XML 创建并启动虚拟机

        Args:
            xml: 虚拟机 XML 定义

        Returns:
            libvirt.virDomain: 新创建的虚拟机对象
        """
        return self.connection.createXML(xml)

    @wrap_libvirt_error
    def get_storage_pools(self, flags: int = 0) -> list:
        """
        获取存储池列表

        Args:
            flags: libvirt 标志位

        Returns:
            list: 存储池对象列表
        """
        return self.connection.listAllStoragePools(flags)

    @wrap_libvirt_error
    def get_networks(self, flags: int = 0) -> list:
        """
        获取网络列表

        Args:
            flags: libvirt 标志位

        Returns:
            list: 网络对象列表
        """
        return self.connection.listAllNetworks(flags)


@contextmanager
def hypervisor_context(uri: str = "qemu:///system") -> Generator[HypervisorManager, None, None]:
    """
    上下文管理器：自动管理 hypervisor 连接

    Args:
        uri: libvirt 连接 URI

    Yields:
        HypervisorManager: 连接管理器实例

    Example:
        >>> with hypervisor_context() as hv:
        >>>     domains = hv.list_domains()
        >>>     for domain in domains:
        >>>         print(domain.name())
    """
    manager = HypervisorManager(uri)
    try:
        manager.connect()
        yield manager
    finally:
        manager.disconnect()


# 全局连接管理器实例
_global_hypervisor_manager: Optional[HypervisorManager] = None


def get_global_hypervisor_manager(uri: str = "qemu:///system") -> HypervisorManager:
    """
    获取全局 hypervisor 管理器实例（单例模式）

    Args:
        uri: libvirt 连接 URI

    Returns:
        HypervisorManager: 全局管理器实例
    """
    global _global_hypervisor_manager

    if _global_hypervisor_manager is None:
        _global_hypervisor_manager = HypervisorManager(uri)

    return _global_hypervisor_manager