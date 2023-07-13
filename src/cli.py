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
    table.add_column("Vm Name", style="dim", width=12)
    table.add_column("Path", style="dim", width=40)
    table.add_column("Power State", style="dim", width=12)
    for vm in vm_list:
        table.add_row(vm.name, vm.path, vm.power_state)
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
              pattern: Annotated[str, typer.Argument(help="The place to store the VM created")]):
    console.print(esxi.create_vm(name=name, datastore=esxi.get_datastore(lambda ds: ds.name == pattern)))


@app.command()
def destroy_vm(pattern: Annotated[str, typer.Argument(help="The name of VM to destroy")]):
    esxi.delete_vm(vm=esxi.get_vm(lambda vm: vm.name == pattern))
    console.print("Done")


@app.command()
def power_on(name: Annotated[str, typer.Argument(help="The name VM to power on")]):
    vim = esxi.get_vm(lambda vm: vm.name == name)
    vim.power_on()
    console.print(f"{vim.name} Powered On")


@app.command()
def power_off(name: Annotated[str, typer.Argument(help="The name VM to power off")]):
    vim = esxi.get_vm(lambda vm: vm.name == name)
    vim.power_off()
    console.print(f"{vim.name} Powered Off")


@app.command()
def suspend(name: Annotated[str, typer.Argument(help="The name VM to suspend")]):
    vim = esxi.get_vm(lambda vm: vm.name == name)
    if format(vim.vim_obj.runtime.powerState) == "poweredOn":
        vim.suspend()
        console.print(f"{vim.name} Suspended")
    else:
        console.print(f"{vim.name} is not powered on")


@app.command()
def import_ovf(name: Annotated[str, typer.Argument(help="The name VM to import")],
               datastore: Annotated[str, typer.Argument(help="The datastore to import to")],
               ovf_url: Annotated[str, typer.Argument(help="The ovf file url")]):
    esxi.import_ovf(name=name,
                    datastore=esxi.get_datastore(lambda ds: ds.name == datastore),
                    ovf_url=ovf_url)


if __name__ == "__main__":
    esxi = ESXi(ip="10.161.162.8", user="root", pwd="CSEQz4d+r8jeM*lS")
    console.print("+++++++++++++++++++++ Connected to ESXi ++++++++++++++++++++++++++++++++")
    app()
    # esxi.import_ovf(name='win11_vm',
    #                 datastore=esxi.get_datastore(
    #                     lambda datastore: datastore.name == 'local-0'),
    #                 ovf_url='http://sftp-eng.eng.vmware.com/vmstorage/qe/windows/windows11/64/111538-Windows-11-v21H2-64-Enterprise-NVMe-Tools/111538-Windows-11-v21H2-64-Enterprise-NVMe-Tools.ovf')

