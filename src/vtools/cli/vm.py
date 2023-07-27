import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from typing_extensions import Annotated

from vtools.cli.config import connect
from vtools.query import by

app = typer.Typer()
console = Console()


@app.command('list')
def query(
    field: Annotated[str, typer.Option(help="The field to filter on")] = None,
    condition: Annotated[str, typer.Option(help="The condition to apply")] = None
):
    if (field is None) ^ (condition is None):
        raise typer.BadParameter(
            "Both 'field' and 'condition' need to be provided together")

    esxi = connect()

    table = Table(show_header=True, header_style="bold magenta")
    if field is None:
        vm_list = esxi.vm_manager().list()
    else:
        vm_list = esxi.vm_manager().list(by(field, eval(condition)))
    table.add_column("Vm Name", style="dim", width=12)
    table.add_column("Path", style="dim", width=40)
    table.add_column("Power State", style="dim", width=12)
    for vm in vm_list:
        table.add_row(vm.name, escape(vm.path), vm.power_state)
    console.print(table)


if __name__ == "__main__":
    app()
