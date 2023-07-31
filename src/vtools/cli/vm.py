import sys

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from typing_extensions import Annotated

from vtools.cli.config import connect
from vtools.query import by

app = typer.Typer()
console = Console()


@app.command(name='list', help='List all the VMs on the host ESXi')
def query(
    field: Annotated[str, typer.Option(help="The field to filter on")] = None,
    condition: Annotated[str, typer.Option(help="The condition to apply")] = None
):
    if (field is None) ^ (condition is None):
        raise typer.BadParameter("Both 'field' and 'condition' need to be provided together")

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


@app.command(name='power_on', help='Power on the VM')
def power_on(vm_name: Annotated[str, typer.Argument(help="The name VM to power on")]):
    esxi = connect()
    vm_obj = esxi.vm_manager().get(lambda vm: vm.name == vm_name)
    vm_obj.power_on()


@app.command(name='power_off', help='Power off the VM')
def power_on(vm_name: Annotated[str, typer.Argument(help="The name VM to power off")]):
    esxi = connect()
    vm_obj = esxi.vm_manager().get(lambda vm: vm.name == vm_name)
    vm_obj.power_off()


@app.command(name='suspend', help='Suspend the VM')
def power_on(vm_name: Annotated[str, typer.Argument(help="The name VM to suspend")]):
    esxi = connect()
    vm_obj = esxi.vm_manager().get(lambda vm: vm.name == vm_name)
    vm_obj.suspend()


@app.command(name='create', help='Create a new VM')
def create_vm(vm_name: Annotated[str, typer.Argument(help="The name of VM to create")],
              datastore: Annotated[str, typer.Option(help="The place to store the VM created")] = 'datastore1',
              annotation: Annotated[str, typer.Option(help="Description of the VM")] = 'Sample',
              memory_size: Annotated[int, typer.Option(help="The size of VM memory ")] = 128,
              guest_id: Annotated[str, typer.Option(help="Short guest OS identifier")] = 'otherGuest',
              num_cpus: Annotated[int, typer.Option(help="The number of CPUs of the VM")] = 1,
              import_ovf: Annotated[bool, typer.Option(help="Choose to import ovf file, must provide ovf url")] = False,
              ovf_url: Annotated[str, typer.Option(help="The ovf file url")] = None):

    if not import_ovf ^ (ovf_url is None):
        raise typer.BadParameter("Both 'import_ovf' and 'ovf_url' need to be provided together")

    esxi = connect()

    if import_ovf:
        console.print(f"The input ovf url is '{ovf_url}'")
        esxi.vm_manager().import_ovf(name=vm_name,
                                     datastore=esxi.datastore_manager().get(lambda ds: ds.name == datastore),
                                     ovf_url=ovf_url)
    else:
        console.print(esxi.vm_manager().create(name=vm_name,
                                               datastore=esxi.datastore_manager().get(lambda ds: ds.name == datastore),
                                               annotation=annotation,
                                               memory_size=memory_size,
                                               guest_id=guest_id,
                                               num_cpus=num_cpus))


@app.command(name='delete', help='Delete a VM')
def delete_vm(vm_name: Annotated[str, typer.Argument(help="The name of VM to destroy")]):
    esxi = connect()
    vm_obj = esxi.vm_manager().get(lambda vm: vm.name == vm_name)
    if vm_obj is None:
        print(f"The VM '{vm_name}' does not exists!")
        sys.exit()
    esxi.vm_manager().delete(vm_obj)
    console.print(f"Deleted {vm_name}")
# @app.command(name='import_ovf', help='import an ovf file to the ESXi Host')
# def import_ovf(name: Annotated[str, typer.Argument(help="The name of the imported VM")],
#                ovf_url: Annotated[str, typer.Argument(help="The ovf file url")],
#                datastore_name: Annotated[str, typer.Option(help="The datastore to import to")] = "datastore1"):
#     esxi = connect()
#     esxi.import_ovf(name=name,
#                     datastore=esxi.datastore_manager().get(lambda ds: ds.name == datastore_name),
#                     ovf_url=ovf_url)


if __name__ == "__main__":
    app()
