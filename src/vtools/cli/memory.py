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

    memory_size = vm_obj.memory_manager().size()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Memory Size (MB)", style="dim")
    table.add_row(str(memory_size))
    console.print(table)


@app.command(name='edit', help='List the Memory Info of the VM')
def edit(vm_name: Annotated[str, typer.Argument(help="The name of the VM to edit")],
         size: Annotated[int, typer.Argument(help="The size of memory to change to")]):
    esxi = connect()

    vm_obj = esxi.vm_manager().get(lambda _: _.name == vm_name)
    if vm_obj is None:
        console.print(f"The VM '{vm_name}' does not exists!")
        sys.exit()

    vm_obj.memory_manager().edit(memory_size=size)
    console.print(f"Memory Size of {vm_name} changes to {size} MB")


if __name__ == "__main__":
    app()
