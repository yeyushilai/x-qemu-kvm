"""
虚拟机管理相关异常定义

该模块定义了项目中的所有自定义异常类，
按照从通用到具体的层次结构组织。
"""


class VMManagerError(Exception):
    """虚拟机管理基类异常"""
    pass


class HypervisorError(VMManagerError):
    """Hypervisor 连接相关异常"""
    pass


class HypervisorConnectionError(HypervisorError):
    """Hypervisor 连接失败异常"""
    pass


class HypervisorNotSupportedError(HypervisorError):
    """不支持的 Hypervisor 类型异常"""
    pass


class VMOperationError(VMManagerError):
    """虚拟机操作相关异常"""
    pass


class VMNotFoundError(VMOperationError):
    """虚拟机未找到异常"""
    pass


class VMAlreadyExistsError(VMOperationError):
    """虚拟机已存在异常"""
    pass


class VMStateError(VMOperationError):
    """虚拟机状态错误异常"""
    pass


class VMOperationNotAllowedError(VMOperationError):
    """虚拟机操作不允许异常"""
    pass


class XMLValidationError(VMManagerError):
    """XML 定义验证失败异常"""
    pass


class StorageError(VMManagerError):
    """存储相关异常"""
    pass


class StoragePoolNotFoundError(StorageError):
    """存储池未找到异常"""
    pass


class StorageVolumeNotFoundError(StorageError):
    """存储卷未找到异常"""
    pass


class NetworkError(VMManagerError):
    """网络相关异常"""
    pass


class NetworkNotFoundError(NetworkError):
    """网络未找到异常"""
    pass


class ConfigurationError(VMManagerError):
    """配置错误异常"""
    pass


# 辅助函数
def wrap_libvirt_error(func):
    """
    装饰器：将 libvirt 异常转换为自定义异常

    Args:
        func: 需要包装的函数

    Returns:
        包装后的函数
    """
    import functools
    import libvirt

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except libvirt.libvirtError as e:
            error_code = e.get_error_code()
            error_message = e.get_error_message()

            # 根据错误代码转换为相应的自定义异常
            if error_code == libvirt.VIR_ERR_NO_DOMAIN:
                raise VMNotFoundError(f"虚拟机未找到: {error_message}") from e
            elif error_code == libvirt.VIR_ERR_OPERATION_FAILED:
                raise VMOperationError(f"虚拟机操作失败: {error_message}") from e
            elif error_code == libvirt.VIR_ERR_NO_CONNECT:
                raise HypervisorConnectionError(f"Hypervisor 连接失败: {error_message}") from e
            else:
                raise VMManagerError(f"libvirt 错误 [{error_code}]: {error_message}") from e
        except Exception as e:
            # 重新抛出其他异常
            raise

    return wrapper