import sys

import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from vtools.cli.config import connect

app = typer.Typer()
console = Console()


@app.command(name='list', help='list all the snapshot of the VM')
def list_snapshot(vm_name: Annotated[str, typer.Argument(help="The name of VM to list its snapshots")]):
    esxi = connect()
    vm_obj = esxi.vm_manager().get(lambda vm: vm.name == vm_name)
    if vm_obj is None:
        print(f"The VM '{vm_name}' does not exists!")
        sys.exit()
    table = Table(show_header=True, header_style="bold magenta")
    snapshots = vm_obj.snapshot_manager().list()
    table.add_column("Snapshot Name", style="dim")
    table.add_column("Description", style="dim")
    for snapshot in snapshots:
        table.add_row(snapshot.name, snapshot.description)
    console.print(table)


@app.command(name='create', help='create a new snapshot of the VM')
def create_snapshot(vm_name: Annotated[str, typer.Argument(help="The VM to take the snapshot")],
                    snapshot_name: Annotated[str, typer.Argument(help="The name of snapshot")]):
    esxi = connect()
    vm_obj = esxi.vm_manager().get(lambda vm: vm.name == vm_name)
    if vm_obj is None:
        print(f"The VM '{vm_name}' does not exists!")
        sys.exit()
    snapshot = vm_obj.snapshot_manager().create_snapshot(name=snapshot_name, description=f"This is a test for {snapshot_name}")
    console.print(snapshot)
    console.print(f"Snapshot '{snapshot_name}' of {vm_obj.name} is created")


@app.command(name='destroy', help='destroy a snapshot of the VM')
def destroy_snapshot(vm_name: Annotated[str, typer.Argument(help="The VM corresponding to the snapshot")],
                     snapshot_name: Annotated[str, typer.Argument(help="The snapshot to destroy")]):
    esxi = connect()
    vm_obj = esxi.vm_manager().get(lambda vm: vm.name == vm_name)
    if vm_obj is None:
        print(f"The VM '{vm_name}' does not exists!")
        sys.exit()
    if vm_obj.snapshot_manager().destroy_snapshot(snapshot_name):
        console.print(f"Snapshot '{snapshot_name}' of {vm_obj.name} is destroyed")


if __name__ == "__main__":
    app()
