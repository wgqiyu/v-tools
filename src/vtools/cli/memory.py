import sys

import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated
from vtools.cli.config import connect

app = typer.Typer()
console = Console()


@app.command(name='info', help='List the Memory Info of the VM')
def query(vm_name: Annotated[str, typer.Argument(help="The name of the VM to show its memory info")]):
    esxi = connect()

    vm_obj = esxi.vm_manager().get(lambda _: _.name == vm_name)
    if vm_obj is None:
        console.print(f"The VM '{vm_name}' does not exists!")
        sys.exit()

    memory_info = vm_obj.memory_manager().info()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("cpu_pkgs", style="dim")
    table.add_column("cpu_cores", style="dim")
    table.add_column("cpu_threads", style="dim")
    table.add_row(str(memory_info.num_pkgs), str(memory_info.num_cores), str(memory_info.num_threads))
    console.print(table)
