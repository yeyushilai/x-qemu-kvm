"""
虚拟机管理 CLI 命令

该模块提供虚拟机管理的命令行接口。
"""

from typing import Optional, List
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
from rich.prompt import Prompt, Confirm

from src.cli.main import app as main_app, console, config, create_progress, show_error, show_success, show_info
from src.services.vm_service import VMService
from src.models.vm import VMCreateRequest, VMUpdateRequest

# 创建子命令应用
app = typer.Typer(
    name="vm",
    help="虚拟机管理命令",
    rich_markup_mode="rich",
)

# 创建服务实例
vm_service = VMService(config.uri)


@app.command("list", help="列出虚拟机")
def list_vms(
    all: bool = typer.Option(
        False,
        "--all", "-a",
        help="显示所有虚拟机（包括非活跃的）",
    ),
    state: Optional[str] = typer.Option(
        None,
        "--state",
        help="按状态过滤 (running, stopped, paused, etc.)",
    ),
    limit: int = typer.Option(
        20,
        "--limit", "-l",
        help="显示数量限制",
        min=1,
        max=100,
    ),
    output: str = typer.Option(
        "table",
        "--output", "-o",
        help="输出格式 (table, json, yaml)",
    ),
):
    """
    列出虚拟机

    显示虚拟机的列表，支持状态过滤和分页。
    """
    try:
        with create_progress("正在获取虚拟机列表..."):
            # 设置过滤条件
            active_only = not all
            inactive_only = False

            if state:
                if state.lower() == "running":
                    active_only = True
                elif state.lower() == "stopped":
                    active_only = False
                    inactive_only = True
                elif state.lower() == "paused":
                    # 需要特殊处理
                    pass

            # 获取虚拟机列表
            result = vm_service.list_vms(
                active_only=active_only,
                inactive_only=inactive_only,
                page=1,
                page_size=limit,
            )

        # 根据输出格式显示
        if output == "json":
            import json
            console.print_json(json.dumps([vm.dict() for vm in result.vms], default=str))
        elif output == "yaml":
            import yaml
            yaml_str = yaml.dump([vm.dict() for vm in result.vms], default_flow_style=False)
            console.print(yaml_str)
        else:  # table
            table = Table(title=f"虚拟机列表 (共 {result.total} 个)", show_header=True, header_style="bold magenta")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("名称", style="green")
            table.add_column("状态", style="yellow")
            table.add_column("内存 (MB)", justify="right")
            table.add_column("CPU", justify="right")
            table.add_column("创建时间", style="dim")

            for vm in result.vms:
                # 状态颜色
                status_color = {
                    "running": "green",
                    "stopped": "red",
                    "paused": "yellow",
                    "shutdown": "orange",
                }.get(vm.status.value, "white")

                table.add_row(
                    vm.id[:8] + "...",
                    vm.name,
                    f"[{status_color}]{vm.status.value}[/{status_color}]",
                    str(vm.memory),
                    str(vm.vcpu),
                    vm.created_at.strftime("%Y-%m-%d %H:%M"),
                )

            console.print(table)

            # 显示分页信息
            if result.total > limit:
                console.print(f"[dim]显示前 {limit} 个虚拟机，使用 --limit 查看更多[/dim]")

    except Exception as e:
        show_error(f"获取虚拟机列表失败: {str(e)}")


@app.command("info", help="查看虚拟机详情")
def vm_info(
    name_or_id: str = typer.Argument(..., help="虚拟机名称或ID"),
    by_uuid: bool = typer.Option(
        False,
        "--uuid",
        help="按UUID查找（默认为按名称查找）",
    ),
    output: str = typer.Option(
        "table",
        "--output", "-o",
        help="输出格式 (table, json, yaml)",
    ),
):
    """
    查看虚拟机详情

    显示指定虚拟机的详细信息。
    """
    try:
        with create_progress("正在获取虚拟机详情..."):
            vm = vm_service.get_vm(name_or_id, by_uuid=by_uuid)

        if output == "json":
            import json
            console.print_json(json.dumps(vm.dict(), default=str))
        elif output == "yaml":
            import yaml
            yaml_str = yaml.dump(vm.dict(), default_flow_style=False)
            console.print(yaml_str)
        else:  # table
            # 基本信息表格
            basic_table = Table(title=f"虚拟机详情: {vm.name}", show_header=False)
            basic_table.add_column("属性", style="cyan")
            basic_table.add_column("值", style="white")

            basic_table.add_row("ID", vm.id)
            basic_table.add_row("UUID", vm.uuid)
            basic_table.add_row("名称", vm.name)

            # 状态颜色
            status_color = {
                "running": "green",
                "stopped": "red",
                "paused": "yellow",
                "shutdown": "orange",
            }.get(vm.status.value, "white")
            basic_table.add_row("状态", f"[{status_color}]{vm.status.value}[/{status_color}]")

            basic_table.add_row("内存", f"{vm.memory} MB")
            basic_table.add_row("CPU", f"{vm.vcpu} 核心")
            basic_table.add_row("创建时间", vm.created_at.strftime("%Y-%m-%d %H:%M:%S"))
            basic_table.add_row("更新时间", vm.updated_at.strftime("%Y-%m-%d %H:%M:%S"))

            # 配置信息表格
            config_table = Table(title="配置信息", show_header=False)
            config_table.add_column("配置项", style="cyan")
            config_table.add_column("值", style="white")

            config_table.add_row("磁盘路径", vm.disk_path)
            config_table.add_row("磁盘格式", vm.disk_format)
            if vm.disk_size:
                config_table.add_row("磁盘大小", f"{vm.disk_size} MB")
            if vm.iso_path:
                config_table.add_row("ISO路径", vm.iso_path)
            config_table.add_row("网络", vm.network)
            config_table.add_row("图形显示", "启用" if vm.graphics else "禁用")
            if vm.graphics_port:
                config_table.add_row("图形端口", str(vm.graphics_port))
            if vm.description:
                config_table.add_row("描述", vm.description)

            # 显示表格
            console.print(basic_table)
            console.print()  # 空行
            console.print(config_table)

            # 如果有运行时信息
            if vm.cpu_usage is not None or vm.memory_usage is not None:
                console.print()  # 空行
                runtime_table = Table(title="运行时信息", show_header=False)
                runtime_table.add_column("指标", style="cyan")
                runtime_table.add_column("值", style="white")

                if vm.cpu_usage is not None:
                    runtime_table.add_row("CPU使用率", f"{vm.cpu_usage:.1f}%")
                if vm.memory_usage is not None:
                    runtime_table.add_row("内存使用", f"{vm.memory_usage} MB")
                if vm.disk_usage is not None:
                    runtime_table.add_row("磁盘使用", f"{vm.disk_usage} MB")
                if vm.ip_addresses:
                    runtime_table.add_row("IP地址", ", ".join(vm.ip_addresses))

                console.print(runtime_table)

    except Exception as e:
        show_error(f"获取虚拟机详情失败: {str(e)}")


@app.command("create", help="创建虚拟机")
def create_vm(
    name: str = typer.Option(..., "--name", "-n", help="虚拟机名称"),
    memory: int = typer.Option(2048, "--memory", "-m", help="内存大小 (MB)", min=256),
    vcpu: int = typer.Option(2, "--vcpu", "-c", help="虚拟CPU数量", min=1),
    disk_path: Path = typer.Option(..., "--disk", "-d", help="磁盘镜像路径"),
    disk_format: str = typer.Option("qcow2", "--format", "-f", help="磁盘格式 (qcow2, raw, etc.)"),
    disk_size: Optional[int] = typer.Option(None, "--disk-size", "-s", help="磁盘大小 (MB)", min=1024),
    iso_path: Optional[Path] = typer.Option(None, "--iso", "-i", help="ISO镜像路径（用于安装）"),
    network: str = typer.Option("default", "--network", help="网络名称"),
    graphics: bool = typer.Option(False, "--graphics", "-g", help="启用图形显示"),
    description: Optional[str] = typer.Option(None, "--description", help="虚拟机描述"),
    interactive: bool = typer.Option(False, "--interactive", help="交互式创建模式"),
    confirm: bool = typer.Option(True, "--confirm/--no-confirm", help="创建前确认"),
):
    """
    创建新虚拟机

    根据提供的配置创建新的虚拟机。
    """
    try:
        # 交互式模式
        if interactive:
            console.print(Panel.fit("[bold cyan]交互式虚拟机创建向导[/bold cyan]", border_style="cyan"))
            name = Prompt.ask("虚拟机名称", default=name)
            memory = int(Prompt.ask("内存大小 (MB)", default=str(memory)))
            vcpu = int(Prompt.ask("虚拟CPU数量", default=str(vcpu)))
            disk_path = Path(Prompt.ask("磁盘镜像路径", default=str(disk_path)))
            disk_format = Prompt.ask("磁盘格式", default=disk_format, choices=["qcow2", "raw", "vmdk", "vdi", "vhd"])
            disk_size_input = Prompt.ask("磁盘大小 (MB，留空使用现有大小)", default="")
            disk_size = int(disk_size_input) if disk_size_input else None
            iso_path_input = Prompt.ask("ISO镜像路径（留空跳过）", default="")
            iso_path = Path(iso_path_input) if iso_path_input else None
            network = Prompt.ask("网络名称", default=network)
            graphics = Confirm.ask("启用图形显示？", default=graphics)
            description = Prompt.ask("虚拟机描述（留空跳过）", default="") or None

        # 创建请求数据
        vm_data = VMCreateRequest(
            name=name,
            memory=memory,
            vcpu=vcpu,
            disk_path=str(disk_path),
            disk_format=disk_format,
            disk_size=disk_size,
            iso_path=str(iso_path) if iso_path else None,
            network=network,
            graphics=graphics,
            description=description,
        )

        # 显示配置摘要
        if confirm or interactive:
            console.print(Panel.fit("[bold yellow]配置摘要[/bold yellow]", border_style="yellow"))
            summary_table = Table(show_header=False)
            summary_table.add_column("项目", style="cyan")
            summary_table.add_column("值", style="white")

            summary_table.add_row("名称", vm_data.name)
            summary_table.add_row("内存", f"{vm_data.memory} MB")
            summary_table.add_row("CPU", str(vm_data.vcpu))
            summary_table.add_row("磁盘路径", vm_data.disk_path)
            summary_table.add_row("磁盘格式", vm_data.disk_format)
            summary_table.add_row("磁盘大小", f"{vm_data.disk_size} MB" if vm_data.disk_size else "使用现有大小")
            summary_table.add_row("ISO路径", vm_data.iso_path or "无")
            summary_table.add_row("网络", vm_data.network)
            summary_table.add_row("图形显示", "启用" if vm_data.graphics else "禁用")
            summary_table.add_row("描述", vm_data.description or "无")

            console.print(summary_table)

            if not Confirm.ask("是否创建虚拟机？", default=True):
                show_info("已取消创建")
                return

        # 创建虚拟机
        with create_progress("正在创建虚拟机..."):
            created_vm = vm_service.create_vm(vm_data)

        show_success(f"虚拟机创建成功: {created_vm.name}")
        console.print(f"[dim]ID: {created_vm.id}[/dim]")
        console.print(f"[dim]UUID: {created_vm.uuid}[/dim]")

    except Exception as e:
        show_error(f"创建虚拟机失败: {str(e)}")


@app.command("start", help="启动虚拟机")
def start_vm(
    name_or_id: str = typer.Argument(..., help="虚拟机名称或ID"),
    by_uuid: bool = typer.Option(
        False,
        "--uuid",
        help="按UUID查找（默认为按名称查找）",
    ),
):
    """
    启动虚拟机

    启动指定的虚拟机。
    """
    try:
        with create_progress(f"正在启动虚拟机 {name_or_id}..."):
            vm = vm_service.start_vm(name_or_id, by_uuid=by_uuid)

        show_success(f"虚拟机启动成功: {vm.name}")
        console.print(f"[dim]状态: {vm.status.value}[/dim]")

    except Exception as e:
        show_error(f"启动虚拟机失败: {str(e)}")


@app.command("stop", help="停止虚拟机")
def stop_vm(
    name_or_id: str = typer.Argument(..., help="虚拟机名称或ID"),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="强制停止（默认为优雅关机）",
    ),
    by_uuid: bool = typer.Option(
        False,
        "--uuid",
        help="按UUID查找（默认为按名称查找）",
    ),
):
    """
    停止虚拟机

    停止指定的虚拟机，支持优雅关机和强制停止。
    """
    try:
        mode = "强制停止" if force else "优雅关机"
        with create_progress(f"正在{mode}虚拟机 {name_or_id}..."):
            vm = vm_service.stop_vm(name_or_id, force=force, by_uuid=by_uuid)

        show_success(f"虚拟机停止成功: {vm.name}")
        console.print(f"[dim]模式: {mode}[/dim]")
        console.print(f"[dim]状态: {vm.status.value}[/dim]")

    except Exception as e:
        show_error(f"停止虚拟机失败: {str(e)}")


@app.command("restart", help="重启虚拟机")
def restart_vm(
    name_or_id: str = typer.Argument(..., help="虚拟机名称或ID"),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="强制重启（默认为优雅重启）",
    ),
    by_uuid: bool = typer.Option(
        False,
        "--uuid",
        help="按UUID查找（默认为按名称查找）",
    ),
):
    """
    重启虚拟机

    重启指定的虚拟机，支持优雅重启和强制重启。
    """
    try:
        mode = "强制重启" if force else "优雅重启"
        with create_progress(f"正在{mode}虚拟机 {name_or_id}..."):
            vm = vm_service.restart_vm(name_or_id, force=force, by_uuid=by_uuid)

        show_success(f"虚拟机重启成功: {vm.name}")
        console.print(f"[dim]模式: {mode}[/dim]")
        console.print(f"[dim]状态: {vm.status.value}[/dim]")

    except Exception as e:
        show_error(f"重启虚拟机失败: {str(e)}")


@app.command("pause", help="暂停虚拟机")
def pause_vm(
    name_or_id: str = typer.Argument(..., help="虚拟机名称或ID"),
    by_uuid: bool = typer.Option(
        False,
        "--uuid",
        help="按UUID查找（默认为按名称查找）",
    ),
):
    """
    暂停虚拟机

    暂停指定的虚拟机。
    """
    try:
        with create_progress(f"正在暂停虚拟机 {name_or_id}..."):
            vm = vm_service.pause_vm(name_or_id, by_uuid=by_uuid)

        show_success(f"虚拟机暂停成功: {vm.name}")
        console.print(f"[dim]状态: {vm.status.value}[/dim]")

    except Exception as e:
        show_error(f"暂停虚拟机失败: {str(e)}")


@app.command("resume", help="恢复虚拟机")
def resume_vm(
    name_or_id: str = typer.Argument(..., help="虚拟机名称或ID"),
    by_uuid: bool = typer.Option(
        False,
        "--uuid",
        help="按UUID查找（默认为按名称查找）",
    ),
):
    """
    恢复虚拟机

    恢复指定的虚拟机。
    """
    try:
        with create_progress(f"正在恢复虚拟机 {name_or_id}..."):
            vm = vm_service.resume_vm(name_or_id, by_uuid=by_uuid)

        show_success(f"虚拟机恢复成功: {vm.name}")
        console.print(f"[dim]状态: {vm.status.value}[/dim]")

    except Exception as e:
        show_error(f"恢复虚拟机失败: {str(e)}")


@app.command("delete", help="删除虚拟机")
def delete_vm(
    name_or_id: str = typer.Argument(..., help="虚拟机名称或ID"),
    delete_disk: bool = typer.Option(
        False,
        "--delete-disk",
        help="同时删除磁盘文件",
    ),
    by_uuid: bool = typer.Option(
        False,
        "--uuid",
        help="按UUID查找（默认为按名称查找）",
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="不确认直接删除",
    ),
):
    """
    删除虚拟机

    删除指定的虚拟机，可选是否删除磁盘文件。
    """
    try:
        # 获取虚拟机信息用于确认
        if not force:
            try:
                vm = vm_service.get_vm(name_or_id, by_uuid=by_uuid)
                console.print(Panel.fit(
                    f"[bold red]将要删除虚拟机[/bold red]\n\n"
                    f"[cyan]名称:[/cyan] {vm.name}\n"
                    f"[cyan]ID:[/cyan] {vm.id}\n"
                    f"[cyan]状态:[/cyan] {vm.status.value}\n"
                    f"[cyan]删除磁盘:[/cyan] {'是' if delete_disk else '否'}",
                    title="删除确认",
                    border_style="red",
                ))

                if not Confirm.ask("确定要删除吗？", default=False):
                    show_info("已取消删除")
                    return
            except Exception:
                # 如果获取信息失败，仍然继续删除
                pass

        with create_progress(f"正在删除虚拟机 {name_or_id}..."):
            vm_service.delete_vm(name_or_id, delete_disk=delete_disk, by_uuid=by_uuid)

        show_success(f"虚拟机删除成功: {name_or_id}")
        if delete_disk:
            console.print("[dim]磁盘文件已删除[/dim]")

    except Exception as e:
        show_error(f"删除虚拟机失败: {str(e)}")


@app.command("console", help="获取虚拟机控制台信息")
def vm_console(
    name_or_id: str = typer.Argument(..., help="虚拟机名称或ID"),
    by_uuid: bool = typer.Option(
        False,
        "--uuid",
        help="按UUID查找（默认为按名称查找）",
    ),
):
    """
    获取虚拟机控制台信息

    显示虚拟机的VNC/SPICE控制台连接信息。
    """
    try:
        with create_progress("正在获取控制台信息..."):
            vm = vm_service.get_vm(name_or_id, by_uuid=by_uuid)

        if not vm.graphics:
            show_error("该虚拟机未启用图形显示")
            return

        console.print(Panel.fit(
            f"[bold cyan]虚拟机控制台信息[/bold cyan]\n\n"
            f"[green]名称:[/green] {vm.name}\n"
            f"[green]VNC/SPICE端口:[/green] {vm.graphics_port or '自动分配'}\n"
            f"[green]连接地址:[/green] localhost:{vm.graphics_port or '5900+'}\n\n"
            f"[dim]使用 VNC 客户端连接以上地址[/dim]\n"
            f"[dim]或使用 noVNC 等 Web 客户端[/dim]",
            title="控制台",
            border_style="cyan",
        ))

    except Exception as e:
        show_error(f"获取控制台信息失败: {str(e)}")


@app.command("stats", help="查看虚拟机统计信息")
def vm_stats(
    name_or_id: str = typer.Argument(..., help="虚拟机名称或ID"),
    by_uuid: bool = typer.Option(
        False,
        "--uuid",
        help="按UUID查找（默认为按名称查找）",
    ),
    interval: int = typer.Option(
        1,
        "--interval", "-i",
        help="刷新间隔（秒）",
        min=1,
        max=60,
    ),
    continuous: bool = typer.Option(
        False,
        "--continuous", "-c",
        help="持续显示统计信息",
    ),
):
    """
    查看虚拟机统计信息

    显示虚拟机的CPU、内存、磁盘、网络等统计信息。
    """
    try:
        # TODO: 实现实时统计信息显示
        show_info("统计信息功能尚未实现")
        console.print("[dim]该功能将在未来版本中实现[/dim]")

    except Exception as e:
        show_error(f"获取统计信息失败: {str(e)}")