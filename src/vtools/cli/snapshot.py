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
    vm_obj = esxi.vms.get(lambda vm: vm.name == vm_name)
    if vm_obj is None:
        console.print(f"The VM '{vm_name}' does not exists!")
        return

    table = Table(show_header=True, header_style="bold magenta")
    snapshots = vm_obj.snapshots.list()
    table.add_column("Snapshot Name", style="dim")
    table.add_column("Description", style="dim")
    for snapshot in snapshots:
        table.add_row(snapshot.name, snapshot.description)
    console.print(table)


@app.command(name='create', help='create a new snapshot of the VM')
def create_snapshot(vm_name: Annotated[str, typer.Option(help="The VM to take the snapshot")],
                    snapshot_name: Annotated[str, typer.Option(help="The name of snapshot")]):
    esxi = connect()
    vm_obj = esxi.vms.get(lambda vm: vm.name == vm_name)
    if vm_obj is None:
        console.print(f"The VM '{vm_name}' does not exists!")
        return

    new_snapshot = vm_obj.snapshots.create(name=snapshot_name, description=f"This is a test for {snapshot_name}")
    console.print(f"Created Snapshot '{snapshot_name}' on VM '{vm_obj.name}'")


@app.command(name='delete', help='destroy a snapshot of the VM')
def destroy_snapshot(vm_name: Annotated[str, typer.Option(help="The VM corresponding to the snapshot")],
                     snapshot_name: Annotated[str, typer.Option(help="The snapshot to destroy")]):
    esxi = connect()
    target_vm = esxi.vms.get(lambda vm: vm.name == vm_name)
    if target_vm is None:
        console.print(f"The VM '{vm_name}' does not exists!")
        return

    target_snapshot = target_vm.snapshots.get(lambda snapshot: snapshot.name == snapshot_name)

    target_vm.snapshots.delete(target_snapshot)
    console.print(f"Deleted Snapshot '{snapshot_name}' on VM '{vm_name}'")


if __name__ == "__main__":
    app()
