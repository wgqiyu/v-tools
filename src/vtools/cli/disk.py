import sys

import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated

from vtools.cli.config import connect
from vtools.query import by

app = typer.Typer()
console = Console()


@app.command(name="list", help='List all the disks attached to a VM')
def query_disk(
        vm_name: Annotated[str, typer.Argument(help="The name of the VM to list disk")],
        field: Annotated[str, typer.Option(help="The field to filter on")] = None,
        condition: Annotated[str, typer.Option(help="The condition to apply")] = None
):
    if (field is None) ^ (condition is None):
        raise typer.BadParameter("Both 'field' and 'condition' need to be provided together")

    esxi = connect()

    vm_obj = esxi.vm_manager().get(lambda vm: vm.name == vm_name)
    if vm_obj is None:
        console.print(f"The VM '{vm_name}' does not exists!")
        sys.exit()

    table = Table(show_header=True, header_style="bold magenta")
    if field is None:
        disks = vm_obj.disk_manager().list()
    else:
        disks = vm_obj.disk_manager().list(by(field, eval(condition)))
    table.add_column("Disk Name", style="dim")
    table.add_column("Size", style="dim")
    for disk in disks:
        table.add_row(disk.name, disk.size)
    console.print(table)


@app.command(name="add", help='Attach a disk to a VM')
def add_disk(vm_name: Annotated[str, typer.Argument(help="The name of the VM to add the disk")],
             disk_size: Annotated[int, typer.Argument(help="The size (in GB) of the disk to add")],
             disk_type: Annotated[str, typer.Option(help="The type of the disk")] = 'thin'):
    esxi = connect()
    vm_obj = esxi.vm_manager().get(lambda vm: vm.name == vm_name)
    if vm_obj is None:
        console.print(f"The VM '{vm_name}' does not exists!")
        sys.exit()
    if vm_obj.disk_manager().add_disk(disk_size, disk_type) is None:
        console.print("Please use the below command:")
        console.print("vtools-cli vm controller add_SCSI <vm_name>")
        sys.exit()
    console.print("A %sGB disk is added to the %s" % (disk_size, vm_obj.vim_obj.config.name))


@app.command(name="remove", help='Remove a disk attached to a VM')
def remove_disk(vm_name: Annotated[str, typer.Argument(help="The name VM to remove disk")],
                disk_number: Annotated[int, typer.Argument(help="The name VM to remove disk")]):
    esxi = connect()
    vm_obj = esxi.vm_manager().get(lambda vm: vm.name == vm_name)
    if vm_obj is None:
        console.print(f"The VM '{vm_name}' does not exists!")
        sys.exit()
    vm_obj.disk_manager().remove_disk(disk_number)
    console.print("The disk %s is removed from %s" % (disk_number, vm_obj.vim_obj.config.name))


if __name__ == "__main__":
    app()
