"""
虚拟机 API 路由

该模块定义了虚拟机的 REST API 端点，
包括虚拟机的创建、删除、启动、停止等操作。
"""

from typing import Optional
from fastapi import APIRouter, Query, Path, HTTPException, status

from src.services.vm_service import VMService
from src.models.vm import (
    VMCreateRequest,
    VMUpdateRequest,
    VMResponse,
    VMDetailResponse,
    VMListResponse,
)

router = APIRouter()
vm_service = VMService()


@router.get("/vms", response_model=VMListResponse, summary="获取虚拟机列表")
async def list_virtual_machines(
    active_only: bool = Query(
        False,
        description="是否只显示活跃的虚拟机"
    ),
    inactive_only: bool = Query(
        False,
        description="是否只显示非活跃的虚拟机"
    ),
    page: int = Query(
        1,
        ge=1,
        description="页码，从1开始"
    ),
    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="每页数量，最大100"
    ),
) -> VMListResponse:
    """
    获取虚拟机列表

    支持分页和状态过滤
    """
    try:
        return vm_service.list_vms(
            active_only=active_only,
            inactive_only=inactive_only,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取虚拟机列表失败: {str(e)}",
        )


@router.post("/vms", response_model=VMDetailResponse, status_code=status.HTTP_201_CREATED, summary="创建虚拟机")
async def create_virtual_machine(
    vm_data: VMCreateRequest,
) -> VMDetailResponse:
    """
    创建新虚拟机

    根据提供的配置创建新的虚拟机
    """
    try:
        return vm_service.create_vm(vm_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"创建虚拟机失败: {str(e)}",
        )


@router.get("/vms/{vm_id}", response_model=VMDetailResponse, summary="获取虚拟机详情")
async def get_virtual_machine(
    vm_id: str = Path(..., description="虚拟机ID（名称或UUID）"),
    by_uuid: bool = Query(
        False,
        description="是否按UUID查找（默认为按名称查找）"
    ),
) -> VMDetailResponse:
    """
    获取虚拟机详情

    通过虚拟机ID（名称或UUID）获取虚拟机详细信息
    """
    try:
        return vm_service.get_vm(vm_id, by_uuid=by_uuid)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"获取虚拟机详情失败: {str(e)}",
        )


@router.put("/vms/{vm_id}", response_model=VMDetailResponse, summary="更新虚拟机配置")
async def update_virtual_machine(
    vm_data: VMUpdateRequest,
    vm_id: str = Path(..., description="虚拟机ID（名称或UUID）"),
    by_uuid: bool = Query(
        False,
        description="是否按UUID查找（默认为按名称查找）"
    ),
) -> VMDetailResponse:
    """
    更新虚拟机配置

    更新虚拟机的内存、CPU等配置
    """
    try:
        return vm_service.update_vm(vm_id, vm_data, by_uuid=by_uuid)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"更新虚拟机配置失败: {str(e)}",
        )


@router.delete("/vms/{vm_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除虚拟机")
async def delete_virtual_machine(
    vm_id: str = Path(..., description="虚拟机ID（名称或UUID）"),
    delete_disk: bool = Query(
        False,
        description="是否同时删除磁盘文件"
    ),
    by_uuid: bool = Query(
        False,
        description="是否按UUID查找（默认为按名称查找）"
    ),
):
    """
    删除虚拟机

    删除指定的虚拟机，可选是否删除磁盘文件
    """
    try:
        vm_service.delete_vm(vm_id, delete_disk=delete_disk, by_uuid=by_uuid)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"删除虚拟机失败: {str(e)}",
        )


@router.post("/vms/{vm_id}/start", response_model=VMResponse, summary="启动虚拟机")
async def start_virtual_machine(
    vm_id: str = Path(..., description="虚拟机ID（名称或UUID）"),
    by_uuid: bool = Query(
        False,
        description="是否按UUID查找（默认为按名称查找）"
    ),
) -> VMResponse:
    """
    启动虚拟机

    启动指定的虚拟机
    """
    try:
        return vm_service.start_vm(vm_id, by_uuid=by_uuid)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"启动虚拟机失败: {str(e)}",
        )


@router.post("/vms/{vm_id}/stop", response_model=VMResponse, summary="停止虚拟机")
async def stop_virtual_machine(
    vm_id: str = Path(..., description="虚拟机ID（名称或UUID）"),
    force: bool = Query(
        False,
        description="是否强制停止（默认为优雅关机）"
    ),
    by_uuid: bool = Query(
        False,
        description="是否按UUID查找（默认为按名称查找）"
    ),
) -> VMResponse:
    """
    停止虚拟机

    停止指定的虚拟机，支持优雅关机和强制停止
    """
    try:
        return vm_service.stop_vm(vm_id, force=force, by_uuid=by_uuid)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"停止虚拟机失败: {str(e)}",
        )


@router.post("/vms/{vm_id}/restart", response_model=VMResponse, summary="重启虚拟机")
async def restart_virtual_machine(
    vm_id: str = Path(..., description="虚拟机ID（名称或UUID）"),
    force: bool = Query(
        False,
        description="是否强制重启（默认为优雅重启）"
    ),
    by_uuid: bool = Query(
        False,
        description="是否按UUID查找（默认为按名称查找）"
    ),
) -> VMResponse:
    """
    重启虚拟机

    重启指定的虚拟机，支持优雅重启和强制重启
    """
    try:
        return vm_service.restart_vm(vm_id, force=force, by_uuid=by_uuid)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"重启虚拟机失败: {str(e)}",
        )


@router.post("/vms/{vm_id}/pause", response_model=VMResponse, summary="暂停虚拟机")
async def pause_virtual_machine(
    vm_id: str = Path(..., description="虚拟机ID（名称或UUID）"),
    by_uuid: bool = Query(
        False,
        description="是否按UUID查找（默认为按名称查找）"
    ),
) -> VMResponse:
    """
    暂停虚拟机

    暂停指定的虚拟机
    """
    try:
        return vm_service.pause_vm(vm_id, by_uuid=by_uuid)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"暂停虚拟机失败: {str(e)}",
        )


@router.post("/vms/{vm_id}/resume", response_model=VMResponse, summary="恢复虚拟机")
async def resume_virtual_machine(
    vm_id: str = Path(..., description="虚拟机ID（名称或UUID）"),
    by_uuid: bool = Query(
        False,
        description="是否按UUID查找（默认为按名称查找）"
    ),
) -> VMResponse:
    """
    恢复虚拟机

    恢复指定的虚拟机
    """
    try:
        return vm_service.resume_vm(vm_id, by_uuid=by_uuid)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"恢复虚拟机失败: {str(e)}",
        )


@router.get("/vms/{vm_id}/stats", summary="获取虚拟机统计信息")
async def get_virtual_machine_stats(
    vm_id: str = Path(..., description="虚拟机ID（名称或UUID）"),
    by_uuid: bool = Query(
        False,
        description="是否按UUID查找（默认为按名称查找）"
    ),
):
    """
    获取虚拟机统计信息

    获取虚拟机的CPU、内存、磁盘、网络等统计信息
    """
    # TODO: 实现统计信息获取
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="统计信息功能尚未实现",
    )


@router.get("/vms/{vm_id}/console", summary="获取虚拟机控制台信息")
async def get_virtual_machine_console(
    vm_id: str = Path(..., description="虚拟机ID（名称或UUID）"),
    by_uuid: bool = Query(
        False,
        description="是否按UUID查找（默认为按名称查找）"
    ),
):
    """
    获取虚拟机控制台信息

    获取虚拟机的VNC/SPICE控制台连接信息
    """
    # TODO: 实现控制台信息获取
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="控制台功能尚未实现",
    )