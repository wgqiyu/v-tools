import typer
from rich.console import Console
from rich.table import Table

from vtools.cli.config import connect

console = Console()
app = typer.Typer()


@app.command('list')
def query():
    esxi = connect()

    table = Table(show_header=True, header_style="bold magenta")
    ds_list = esxi.datastore_manager().list()
    table.add_column("Datastore Name", style="dim", width=40)
    table.add_column("Type", style="dim", width=8)
    for ds in ds_list:
        table.add_row(ds.name, ds.type)
    console.print(table)


if __name__ == "__main__":
    app()
