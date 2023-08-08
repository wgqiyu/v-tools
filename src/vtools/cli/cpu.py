import sys

import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from vtools.cli.config import connect
from vtools.query import by

app = typer.Typer()
console = Console()


@app.command(name='list', help='List the CPU Info of the VM')
def query(
    vm_name: Annotated[str, typer.Argument(help="The name of the VM to list CPUs")],
    field: Annotated[str, typer.Option(help="The field to filter on, i.e. idx")] = None,
    condition: Annotated[str, typer.Option(help="The condition to apply, i.e. "
                                                "lambda val: val == '<idx>'")] = None
):
    if (field is None) ^ (condition is None):
        raise typer.BadParameter("Both 'field' and 'condition' need to be provided together")

    esxi = connect()

    vm_obj = esxi.vm_manager().get(lambda _: _.name == vm_name)
    if vm_obj is None:
        console.print(f"The VM '{vm_name}' does not exists!")
        sys.exit()

    cpu_info = vm_obj.cpu_manager().info()
    table1 = Table(show_header=True, header_style="bold magenta")
    table1.add_column("cpu_pkgs", style="dim")
    table1.add_column("cpu_cores", style="dim")
    table1.add_column("cpu_threads", style="dim")
    table1.add_row(str(cpu_info.num_pkgs), str(cpu_info.num_cores), str(cpu_info.num_threads))
    console.print(table1)

    table2 = Table(show_header=True, header_style="bold magenta")
    if field is None:
        cpu_list = vm_obj.cpu_manager().list()
    else:
        cpu_list = vm_obj.cpu_manager().list(by(field, eval(condition)))
    table2.add_column("Index", style="dim")
    table2.add_column("Description", style="dim")
    for cpu in cpu_list:
        table2.add_row(str(cpu.idx), cpu.description)
    console.print(table2)
