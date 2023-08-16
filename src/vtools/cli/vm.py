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
from vtools.vm import (
    from_ovf,
    from_scratch
)
from vtools.query import by_name

console = Console()

app = typer.Typer()

create_app = typer.Typer()
app.add_typer(create_app, name="create", help="Create VM")

app.add_typer(disk.app, name="disk", help="Operations related to Disk")
app.add_typer(snapshot.app, name="snapshot", help="Operations related to Snapshot")


@app.command(name='list', help='List VMs')
def query(
    field: Annotated[str, typer.Option(help="The field to filter on")] = None,
    condition: Annotated[str, typer.Option(help="The condition to apply, i.e. lambda val: val == 'vm1'")] = None
):
    if (field is None) ^ (condition is None):
        raise typer.BadParameter("Both 'field' and 'condition' need to be provided together")

    esxi = connect()

    table = Table(show_header=True, header_style="bold magenta")
    if field is None:
        vm_list = esxi.vms.list()
    else:
        vm_list = esxi.vms().list(by(field, eval(condition)))
    table.add_column("Vm Name", style="dim")
    table.add_column("Primary IP", style="dim")
    table.add_column("Path", style="dim")
    table.add_column("Power State", style="dim")
    table.add_column("Memory", style="dim")
    table.add_column("CPUs", style="dim")
    for vm in vm_list:
        table.add_row(vm.name, vm.primary_ip, escape(vm.path),
                      vm.power_state, str(vm.memory.size_in_mb),
                      str(vm.cpu.number))
    console.print(table)


@app.command(name='power_on', help='Power on the VM')
def power_on(vm_name: Annotated[str, typer.Argument(help="The name VM to power on")]):
    esxi = connect()
    vm_obj = esxi.vms.get(lambda vm: vm.name == vm_name)
    vm_obj.power_on()


@app.command(name='power_off', help='Power off the VM')
def power_off(vm_name: Annotated[str, typer.Argument(help="The name VM to power off")]):
    esxi = connect()
    vm_obj = esxi.vms.get(lambda vm: vm.name == vm_name)
    vm_obj.power_off()


@app.command(name='suspend', help='Suspend the VM')
def suspend(vm_name: Annotated[str, typer.Argument(help="The name VM to suspend")]):
    esxi = connect()
    vm_obj = esxi.vms.get(lambda vm: vm.name == vm_name)
    vm_obj.suspend()


@create_app.command(name='from_ovf', help='Create a new VM from OVF')
def create_from_ovf(vm_name: Annotated[str, typer.Option(help="The name of VM to create")],
                    ovf_url: Annotated[str, typer.Option(help="The ovf file url")],
                    datastore: Annotated[str, typer.Option(help="The place to store the VM created")]):
    esxi = connect()
    import_spec = from_ovf(ovf_url)

    new_vm = esxi.vms.create(
        name=vm_name,
        spec=import_spec,
        datastore=esxi.datastores.get(by_name(lambda v: v == datastore))
    )
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Vm Name", style="dim")
    table.add_column("Path", style="dim")
    table.add_column("Memory", style="dim")
    table.add_column("CPUs", style="dim")

    table.add_row(new_vm.name, escape(new_vm.path),
                  str(new_vm.memory.size_in_mb), str(new_vm.cpu.number))
    console.print(table)


@create_app.command(name='from_scratch', help='Create a new VM from scratch')
def create_from_scratch(vm_name: Annotated[str, typer.Option(help="The name of VM to create")],
                        datastore: Annotated[str, typer.Option(help="The place to store the VM created")],
                        cpu_number: Annotated[int, typer.Option(help="The number of CPUs of the VM")] = 1,
                        cpu_cores_per_socket: Annotated[int, typer.Option(help="The CPU cores per socket of the VM")] = 1,
                        memory_size: Annotated[int, typer.Option(help="The size of VM memory in MB")] = 128,
                        guest_id: Annotated[str, typer.Option(help="Short guest OS identifier")] = 'otherGuest'):
    esxi = connect()
    create_spec = from_scratch(esxi.get_vm_config_option())
    create_spec.set_cpu(cpu_number, cpu_cores_per_socket)
    create_spec.set_memory(memory_size)
    create_spec.set_guest(guest_id)

    new_vm = esxi.vms.create(
        name=vm_name,
        spec=create_spec,
        datastore=esxi.datastores.get(by_name(lambda v: v == datastore))
    )
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Vm Name", style="dim")
    table.add_column("Path", style="dim")
    table.add_column("Memory", style="dim")
    table.add_column("CPUs", style="dim")

    table.add_row(new_vm.name, escape(new_vm.path),
                  str(new_vm.memory.size_in_mb), str(new_vm.cpu.number))
    console.print(table)


@app.command(help='Delete a VM')
def delete(vm_name: Annotated[str, typer.Option(help="The name of VM to destroy")]):
    esxi = connect()

    target_vm = esxi.vms.get(lambda vm: vm.name == vm_name)
    if not target_vm:
        console.print(f'Failed to find VM "{vm_name}"!')
        return
    esxi.vms.delete(target_vm)
    console.print(f'Deleted VM "{vm_name}"')


if __name__ == "__main__":
    app()
