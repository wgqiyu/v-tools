import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from vtools.cli.config import connect
from vtools.query import by

console = Console()
app = typer.Typer()


@app.command(name='list', help='list all the Datastore on the host ESXi')
def query(
    field: Annotated[str, typer.Option(help="The field to filter on")] = None,
    condition: Annotated[str, typer.Option(help="The condition to apply")] = None
):
    if (field is None) ^ (condition is None):
        raise typer.BadParameter("Both 'field' and 'condition' need to be provided together")

    esxi = connect()

    table = Table(show_header=True, header_style="bold magenta")
    if field is None:
        ds_list = esxi.datastore_manager().list()
    else:
        ds_list = esxi.datastore_manager().list(by(field, eval(condition)))
    table.add_column("Datastore Name", style="dim", width=40)
    table.add_column("Type", style="dim", width=8)
    for ds in ds_list:
        table.add_row(ds.name, ds.type)
    console.print(table)


if __name__ == "__main__":
    app()
