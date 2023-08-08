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
def query_controller(
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
        controllers = vm_obj.controller_manager().list()
    else:
        controllers = vm_obj.controller_manager().list(by(field, eval(condition)))
    table.add_column("Controller Name", style="dim")
    table.add_column("Description", style="dim")
    for controller in controllers:
        table.add_row(controller.name, controller.description)
    console.print(table)


@app.command(name='add_SCSI', help='add scsi controller for disk management')
def add_scsi_controller(vm_name: Annotated[str, typer.Argument(help="The name VM to add controller")]):
    esxi = connect()

    vm_obj = esxi.vm_manager().get(lambda vm: vm.name == vm_name)
    if vm_obj is None:
        console.print(f"The VM '{vm_name}' does not exists!")
        sys.exit()
    vm_obj.controller_manager().add_scsi_controller()
    console.print(f"Added ParaVirtualSCSIController to {vm_name}")


@app.command(name='remove_SCSI', help='remove scsi controller for disk management')
def remove_scsi_controller(vm_name: Annotated[str, typer.Argument(help="The name VM to remove controller")],
                           controller_number: Annotated[int, typer.Argument(help="The name VM to remove disk")]):
    esxi = connect()

    vm_obj = esxi.vm_manager().get(lambda vm: vm.name == vm_name)
    if vm_obj is None:
        console.print(f"The VM '{vm_name}' does not exists!")
        sys.exit()
    vm_obj.controller_manager().remove_scsi_controller(controller_number)
    console.print(f"Removed ParaVirtualSCSIController{controller_number} from {vm_name}")
