import sys

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from typing_extensions import Annotated

from vtools.cli import (
    disk,
    snapshot
)

from vtools.cli.config import connect
from vtools.query import by

app = typer.Typer()
console = Console()
app.add_typer(disk.app, name="disk", help="Operations related to Disk")
app.add_typer(snapshot.app, name="snapshot", help="Operations related to Snapshot")


@app.command(name='list', help='List all the VMs on the host ESXi')
def query(
    field: Annotated[str, typer.Option(help="The field to filter on")] = None,
    condition: Annotated[str, typer.Option(help="The condition to apply, i.e. lambda val: val == 'vm1'")] = None
):
    if (field is None) ^ (condition is None):
        raise typer.BadParameter("Both 'field' and 'condition' need to be provided together")

    esxi = connect()

    table = Table(show_header=True, header_style="bold magenta")
    if field is None:
        vm_list = esxi.vm_manager().list()
    else:
        vm_list = esxi.vm_manager().list(by(field, eval(condition)))
    table.add_column("Vm Name", style="dim")
    table.add_column("Primary IP", style="dim")
    table.add_column("Path", style="dim")
    table.add_column("Power State", style="dim")
    table.add_column("Memory", style="dim")
    table.add_column("CPUs", style="dim")
    for vm in vm_list:
        table.add_row(vm.name, vm.primary_ip, escape(vm.path), vm.power_state, str(vm.memory), str(vm.num_cpus))
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
              ds: Annotated[str, typer.Option(help="The place to store the VM created")] = 'datastore1',
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
        console.print(f"The input ovf url is '{ovf_url}'. This might takes 5~10 minutes...")
        console.print(esxi.vm_manager().import_ovf(name=vm_name,
                                                   datastore=esxi.datastore_manager().get(lambda _: _.name == ds),
                                                   ovf_url=ovf_url))
    else:
        console.print(esxi.vm_manager().create(name=vm_name,
                                               datastore=esxi.datastore_manager().get(lambda _: _.name == ds),
                                               annotation=annotation,
                                               memory_size=memory_size,
                                               guest_id=guest_id,
                                               num_cpus=num_cpus))


@app.command(name='edit', help='Edit an existing VM')
def edit_vm(vm_name: Annotated[str, typer.Argument(help="The VM to edit")],
            new_name: Annotated[str, typer.Option(help="The new name of VM to edit")] = None,
            datastore: Annotated[str, typer.Option(help="The place to store the VM created")] = "datastore1",
            annotation: Annotated[str, typer.Option(help="Description of the VM")] = None,
            memory_size: Annotated[int, typer.Option(help="The size of VM memory ")] = None,
            guest_id: Annotated[str, typer.Option(help="Short guest OS identifier")] = None,
            num_cpus: Annotated[int, typer.Option(help="The number of CPUs of the VM")] = None):
    esxi = connect()
    vm_obj = esxi.vm_manager().get(lambda vm: vm.name == vm_name)
    if vm_obj is None:
        console.print(f"The VM '{vm_name}' does not exists!")
        sys.exit()
    config = vm_obj.vim_obj.config

    info = esxi.vm_manager().edit(vm=vm_obj,
                                  new_name=new_name if new_name else config.name,
                                  datastore=esxi.datastore_manager().get(lambda ds: ds.name == datastore),
                                  annotation=annotation if annotation else config.annotation,
                                  memory_size=memory_size if memory_size else config.hardware.memoryMB,
                                  guest_id=guest_id if guest_id else config.guestId,
                                  num_cpus=num_cpus if num_cpus else config.hardware.numCPU)

    console.print(f"Reconfigured {vm_name} to {info}")


@app.command(name='delete', help='Delete a VM')
def delete_vm(vm_name: Annotated[str, typer.Argument(help="The name of VM to destroy")]):
    esxi = connect()
    vm_obj = esxi.vm_manager().get(lambda vm: vm.name == vm_name)
    if vm_obj is None:
        console.print(f"The VM '{vm_name}' does not exists!")
        sys.exit()
    esxi.vm_manager().delete(vm_obj)
    console.print(f"Deleted {vm_name}")


if __name__ == "__main__":
    app()
