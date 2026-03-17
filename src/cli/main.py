"""
vmctl - 虚拟机生命周期管理 CLI

基于 Typer 构建的命令行工具，提供虚拟机管理的交互式界面。
"""

import sys
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

from src.cli.commands import vm

# 配置日志
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 创建 Typer 应用
app = typer.Typer(
    name="vmctl",
    help="虚拟机生命周期管理命令行工具",
    add_completion=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)

# 创建 Rich 控制台
console = Console()

# 全局配置
class Config:
    """全局配置类"""
    def __init__(self):
        self.verbose = False
        self.uri = "qemu:///system"
        self.config_file = Path.home() / ".vmctl" / "config.yaml"

config = Config()


@app.callback()
def main(
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="启用详细输出",
    ),
    uri: str = typer.Option(
        "qemu:///system",
        "--uri",
        help="libvirt 连接 URI (例如: qemu:///system, qemu:///session)",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        help="配置文件路径",
    ),
):
    """
    x-qemu-kvm 虚拟机管理命令行工具

    提供完整的虚拟机生命周期管理功能，包括：
    - 创建、删除虚拟机
    - 启动、停止、重启虚拟机
    - 暂停、恢复虚拟机
    - 查看虚拟机状态和统计信息
    - 管理存储和网络资源

    使用示例:
        vmctl vm list                    # 列出所有虚拟机
        vmctl vm create --name my-vm ... # 创建虚拟机
        vmctl vm start my-vm            # 启动虚拟机
        vmctl vm stop my-vm             # 停止虚拟机
    """
    # 更新配置
    config.verbose = verbose
    config.uri = uri
    if config_file:
        config.config_file = config_file

    # 设置日志级别
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("详细模式已启用")

    logger.debug(f"使用 URI: {uri}")
    logger.debug(f"配置文件: {config.config_file}")


# 添加子命令
app.add_typer(vm.app, name="vm", help="虚拟机管理命令")


@app.command("version", help="显示版本信息")
def version():
    """显示版本信息"""
    from importlib.metadata import version, PackageNotFoundError

    try:
        package_version = version("x-qemu-kvm")
    except PackageNotFoundError:
        package_version = "0.1.0 (开发版)"

    rprint(Panel.fit(
        f"[bold cyan]x-qemu-kvm[/bold cyan] v{package_version}\n"
        f"[dim]虚拟机生命周期管理工具[/dim]\n"
        f"[dim]作者: 杨壮 (John Young) <john.young@foxmai.com>[/dim]",
        title="版本信息",
        border_style="cyan",
    ))


@app.command("config", help="显示当前配置")
def show_config():
    """显示当前配置"""
    table = Table(title="当前配置", show_header=True, header_style="bold magenta")
    table.add_column("配置项", style="cyan")
    table.add_column("值", style="green")

    table.add_row("Verbose", str(config.verbose))
    table.add_row("URI", config.uri)
    table.add_row("配置文件", str(config.config_file))
    table.add_row("配置文件存在", str(config.config_file.exists()))

    console.print(table)


@app.command("check", help="检查环境")
def check_environment():
    """检查运行环境"""
    checks = []

    # 检查 Python 版本
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks.append(("Python 版本", python_version, "✓" if sys.version_info >= (3, 11) else "✗"))

    # 检查 libvirt-python
    try:
        import libvirt
        libvirt_version = libvirt.getVersion()
        libvirt_version_str = f"{libvirt_version // 1000000}.{(libvirt_version // 1000) % 1000}.{libvirt_version % 1000}"
        checks.append(("libvirt-python", libvirt_version_str, "✓"))
    except ImportError:
        checks.append(("libvirt-python", "未安装", "✗"))

    # 检查配置文件目录
    config_dir = config.config_file.parent
    checks.append(("配置目录", str(config_dir), "✓" if config_dir.exists() else "⚠"))

    # 显示检查结果
    table = Table(title="环境检查", show_header=True, header_style="bold magenta")
    table.add_column("检查项", style="cyan")
    table.add_column("状态", style="green")
    table.add_column("结果", style="yellow")

    for check_name, status, result in checks:
        table.add_row(check_name, status, result)

    console.print(table)

    # 总结
    all_passed = all(result in ("✓", "⚠") for _, _, result in checks)
    if all_passed:
        console.print("[green]✓ 环境检查通过[/green]")
    else:
        console.print("[red]✗ 环境检查未通过，请解决上述问题[/red]")


@app.command("docs", help="打开文档")
def open_docs():
    """打开项目文档"""
    import webbrowser

    docs_url = "https://github.com/yourusername/x-qemu-kvm"
    console.print(f"[cyan]正在打开文档: {docs_url}[/cyan]")
    try:
        webbrowser.open(docs_url)
    except Exception as e:
        console.print(f"[red]无法打开浏览器: {e}[/red]")
        console.print(f"[yellow]请手动访问: {docs_url}[/yellow]")


# 错误处理
def show_error(message: str, details: Optional[str] = None):
    """显示错误信息"""
    error_panel = Panel.fit(
        f"[bold red]{message}[/bold red]\n\n[dim]{details}[/dim]" if details else f"[bold red]{message}[/bold red]",
        title="错误",
        border_style="red",
    )
    console.print(error_panel)


def show_success(message: str):
    """显示成功信息"""
    success_panel = Panel.fit(
        f"[bold green]{message}[/bold green]",
        title="成功",
        border_style="green",
    )
    console.print(success_panel)


def show_warning(message: str):
    """显示警告信息"""
    warning_panel = Panel.fit(
        f"[bold yellow]{message}[/bold yellow]",
        title="警告",
        border_style="yellow",
    )
    console.print(warning_panel)


def show_info(message: str):
    """显示信息"""
    info_panel = Panel.fit(
        f"[bold cyan]{message}[/bold cyan]",
        title="信息",
        border_style="cyan",
    )
    console.print(info_panel)


# 进度条工具
def create_progress(description: str = "处理中..."):
    """创建进度条"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    )


# 导出工具函数
__all__ = [
    "app",
    "console",
    "config",
    "show_error",
    "show_success",
    "show_warning",
    "show_info",
    "create_progress",
]


if __name__ == "__main__":
    app()