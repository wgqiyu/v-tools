from rich.console import Console
from rich.table import Table

from vtools import ESXi


if __name__ == "__main__":
    console = Console()

    esxi = ESXi(ip="10.187.96.254", user="root", pwd="PGESn3ppb7g-P-Hp")

    esxi.import_ovf(name='win11_vm',
                    datastore=esxi.get_datastore(
                        lambda datastore: datastore.name == 'local-0'),
                    ovf_url='http://sftp-eng.eng.vmware.com/vmstorage/qe/windows/windows11/64/111538-Windows-11-v21H2-64-Enterprise-NVMe-Tools/111538-Windows-11-v21H2-64-Enterprise-NVMe-Tools.ovf')

    table = Table(show_header=True, header_style="bold magenta")
    vm_list = esxi.list_vm()
    table.add_column("Vm Name", style="dim", width=12)
    for vm in vm_list:
        table.add_row(vm.name)

    console.print(table)
