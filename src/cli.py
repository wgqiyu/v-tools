import typer
from rich.console import Console
from rich.table import Table
from typing_extensions import Annotated
from vtools import ESXi
import re

app = typer.Typer()
console = Console()


def check_criteria(vim_obj: str, by: str, pattern: str):
    if vim_obj == "vm":
        if by is None:
            return esxi.list_vm()
        if by == "name":
            return esxi.list_vm(lambda vm: re.search(pattern, vm.name) is not None)
        if by == "path":
            return esxi.list_vm(lambda vm: re.search(pattern, vm.path) is not None)
    if vim_obj == "datastore":
        if by is None:
            return esxi.list_datastore()
        if by == "name":
            return esxi.list_datastore(lambda ds: re.search(pattern, ds.name) is not None)
        if by == "type":
            return esxi.list_datastore(lambda ds: re.search(pattern, ds.type) is not None)


@app.command()
def list_vm(by: Annotated[str, typer.Option(help="The criteria for searching VMs")] = None,
            pattern: Annotated[str, typer.Option(help="The pattern of VM to search for")] = None):
    table = Table(show_header=True, header_style="bold magenta")
    vm_list = check_criteria("vm", by, pattern)
    table.add_column("Vm Name", style="dim")
    table.add_column("Path", style="dim")
    table.add_column("Power State", style="dim")
    table.add_column("Memory Size", style="dim")
    table.add_column("Num CPUs", style="dim")
    for vm in vm_list:
        table.add_row(vm.name, vm.path, vm.power_state, str(vm.memory), str(vm.num_cpus))
    console.print(table)


@app.command()
def list_datastore(by: Annotated[str, typer.Option(help="The criteria for searching Datastore")] = None,
                   pattern: Annotated[str, typer.Option(help="The pattern of Datastore to search for")] = None):
    table = Table(show_header=True, header_style="bold magenta")
    ds_list = check_criteria("datastore", by, pattern)
    table.add_column("Datastore Name", style="dim", width=40)
    table.add_column("Type", style="dim", width=8)
    for ds in ds_list:
        table.add_row(ds.name, ds.type)
    console.print(table)


@app.command()
def create_vm(name: Annotated[str, typer.Argument(help="The name of VM to create")],
              datastore: Annotated[str, typer.Argument(help="The place to store the VM created")],
              annotation: Annotated[str, typer.Option(help="Description of the VM")] = 'Sample',
              memory_size: Annotated[int, typer.Option(help="The size of VM memory ")] = 128,
              guest_id: Annotated[str, typer.Option(help="Short guest OS identifier")] = 'otherGuest',
              num_cpus: Annotated[int, typer.Option(help="The number of CPUs of the VM")] = 1):
    console.print(esxi.create_vm(name=name,
                                 datastore=esxi.get_datastore(lambda ds: ds.name == datastore),
                                 annotation=annotation,
                                 memory_size=memory_size,
                                 guest_id=guest_id,
                                 num_cpus=num_cpus))


@app.command()
def destroy_vm(pattern: Annotated[str, typer.Argument(help="The name of VM to destroy")]):
    esxi.delete_vm(vm=esxi.get_vm(lambda vm: vm.name == pattern))
    console.print("Done")


@app.command()
def power_on(name: Annotated[str, typer.Argument(help="The name VM to power on")]):
    vm_obj = esxi.get_vm(lambda vm: vm.name == name)
    if format(vm_obj.vim_obj.runtime.powerState) != "poweredOn":
        console.print(f"{vm_obj.name} is already powered on")
    else:
        vm_obj.power_on()
        console.print(f"{vm_obj.name} Powered On")


@app.command()
def power_off(name: Annotated[str, typer.Argument(help="The name VM to power off")]):
    vm_obj = esxi.get_vm(lambda vm: vm.name == name)
    if format(vm_obj.vim_obj.runtime.powerState) != "poweredOff":
        vm_obj.power_off()
        console.print(f"{vm_obj.name} Powered Off")
    else:
        console.print(f"{vm_obj.name} is not powered off")


@app.command()
def suspend(name: Annotated[str, typer.Argument(help="The name VM to suspend")]):
    vm_obj = esxi.get_vm(lambda vm: vm.name == name)
    if format(vm_obj.vim_obj.runtime.powerState) == "poweredOn":
        vm_obj.suspend()
        console.print(f"{vm_obj.name} Suspended")
    else:
        console.print(f"{vm_obj.name} is not powered on")


@app.command()
def list_snapshot(name: Annotated[str, typer.Argument(help="The name of VM to list its snapshots")]):
    vm_obj = esxi.get_vm(lambda vm: vm.name == name)
    snapshots = vm_obj.list_snapshot()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Snapshot Name", style="dim")
    table.add_column("Snapshot Description", style="dim")
    for snapshot in snapshots:
        table.add_row(snapshot.name, snapshot.description)
    console.print(table)


@app.command()
def create_snapshot(snapshot_name: Annotated[str, typer.Argument(help="The name of snapshot")],
                    name: Annotated[str, typer.Argument(help="The VM to take the snapshot")]):
    vm_obj = esxi.get_vm(lambda vm: vm.name == name)
    snapshot = vm_obj.create_snapshot(name=snapshot_name, description="This is a test for snapshot")
    if snapshot:
        console.print(snapshot)
        console.print(f"Snapshot '{snapshot_name}' of {vm_obj.name} is created")


@app.command()
def destroy_snapshot(snapshot_name: Annotated[str, typer.Argument(help="The snapshot to destroy")],
                     name: Annotated[str, typer.Argument(help="The VM corresponding to the snapshot")]):
    vm_obj = esxi.get_vm(lambda vm: vm.name == name)
    if vm_obj.destroy_snapshot(snapshot_name):
        console.print(f"Snapshot '{snapshot_name}' of {vm_obj.name} is destroyed")


@app.command()
def import_ovf(name: Annotated[str, typer.Argument(help="The name VM to import")],
               datastore: Annotated[str, typer.Argument(help="The datastore to import to")],
               ovf_url: Annotated[str, typer.Argument(help="The ovf file url")]):
    esxi.import_ovf(name=name,
                    datastore=esxi.get_datastore(lambda ds: ds.name == datastore),
                    ovf_url=ovf_url)


@app.command()
def check_connection_config():
    with open("connection_config.txt", "r") as file:
        info = file.readlines()
        if len(lines) >= 3:
            console.print(f'ip={info[0].strip()}')
            console.print(f'user={info[1].strip()}')
            console.print(f'pwd={info[2].strip()}\n')
        else:
            console.print("Insufficient lines in the config file.")


@app.command()
def change_connection_config(ip: Annotated[str, typer.Option(help="The host ip to connect to")],
                             user: Annotated[str, typer.Option(help="The user name of host ip")],
                             pwd: Annotated[str, typer.Option(help="The password of host ip")],):
    with open("connection_config.txt", "w") as file:
        file.write(f"{ip}\n")
        file.write(f"{user}\n")
        file.write(f"{pwd}\n")

    with open("connection_config.txt", "r") as file:
        info = file.readlines()
        console.print(f"Changed the config file to:\n"
                      f"ip={info[0].strip()}\n"
                      f"user={info[1].strip()}\n"
                      f"pwd={info[2].strip()}\n")


if __name__ == "__main__":
    with open("connection_config.txt", "r") as config_file:
        lines = config_file.readlines()
        if len(lines) >= 3:
            esxi = ESXi(ip=lines[0].strip(), user=lines[1].strip(), pwd=lines[2].strip())
            console.print("+++++++++++++++++++++ Connected to ESXi ++++++++++++++++++++++++")
        else:
            console.print("Invalid config file. Need to use change-connection-config command.")
    app()

    # esxi = ESXi(ip="10.161.162.8", user="root", pwd="CSEQz4d+r8jeM*lS")

    # esxi.import_ovf(name='win11_vm',
    #                 datastore=esxi.get_datastore(
    #                     lambda datastore: datastore.name == 'local-0'),
    #                 ovf_url='http://sftp-eng.eng.vmware.com/vmstorage/qe/windows/windows11/64/111538-Windows-11-v21H2-64-Enterprise-NVMe-Tools/111538-Windows-11-v21H2-64-Enterprise-NVMe-Tools.ovf')

