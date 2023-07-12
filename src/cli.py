import typer
from rich.console import Console
from rich.table import Table

from vtools import ESXi

app = typer.Typer()
console = Console()


def check_criteria(vim_obj: str, criteria: str, rule: str):
    if vim_obj == "vm":
        if criteria == "name":
            return esxi.list_vm(lambda vm: vm.name == rule)
        if criteria == "path":
            return esxi.list_vm(lambda vm: vm.path == rule)
    if vim_obj == "datastore":
        if criteria == "name":
            return esxi.list_datastore(lambda ds: ds.name == rule)
        if criteria == "type":
            return esxi.list_datastore(lambda ds: ds.type == rule)


@app.command()
def list_vm(criteria: str, rule: str):
    table = Table(show_header=True, header_style="bold magenta")
    vm_list = check_criteria("vm", criteria, rule)
    table.add_column("Vm Name", style="dim", width=12)
    table.add_column("Path", style="dim", width=40)
    table.add_column("Power State", style="dim", width=12)
    for vm in vm_list:
        table.add_row(vm.name, vm.path, vm.power_state)
    console.print(table)


@app.command()
def list_datastore(criteria: str, rule: str):
    table = Table(show_header=True, header_style="bold magenta")
    ds_list = check_criteria("datastore", criteria, rule)
    table.add_column("Datastore Name", style="dim", width=40)
    table.add_column("Type", style="dim", width=8)
    for ds in ds_list:
        table.add_row(ds.name, ds.type)
    console.print(table)


@app.command()
def create_vm(name: str, criteria: str, rule: str):
    if criteria == "name":
        console.print(esxi.create_vm(name=name, datastore=esxi.get_datastore(lambda ds: ds.name == rule)))
    if criteria == "type":
        console.print(esxi.create_vm(name=name, datastore=esxi.get_datastore(lambda ds: ds.type == rule)))


@app.command()
def destroy_vm(criteria: str, rule: str):
    if criteria == "name":
        esxi.delete_vm(vm=esxi.get_vm(lambda vm: vm.name == rule))
    if criteria == "path":
        esxi.delete_vm(vm=esxi.get_vm(lambda vm: vm.path == rule))


if __name__ == "__main__":
    esxi = ESXi(ip="10.161.162.8", user="root", pwd="CSEQz4d+r8jeM*lS")
    print("+++++++++++++++++++++ Connected to ESXi ++++++++++++++++++++++++++++++++")
    app()

    # esxi.import_ovf(name='win11_vm',
    #                 datastore=esxi.get_datastore(
    #                     lambda datastore: datastore.name == 'local-0'),
    #                 ovf_url='http://sftp-eng.eng.vmware.com/vmstorage/qe/windows/windows11/64/111538-Windows-11-v21H2-64-Enterprise-NVMe-Tools/111538-Windows-11-v21H2-64-Enterprise-NVMe-Tools.ovf')

