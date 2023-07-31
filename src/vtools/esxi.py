import sys
from typing import (
    List
)

from pyVim.connect import SmartConnect
from pyVmomi import vim

from vtools.vsphere import get_first_vim_obj, create_config_spec, create_http_nfc_lease,\
    deploy_vm_with_pull_mode, create_import_spec
from vtools.query import QueryMixin
from vtools.vm import VM
from vtools.datastore import Datastore
from pyVim.task import WaitForTask


class ESXi:
    def __init__(
        self,
        ip: str = 'localhost',
        user: str = 'root',
        pwd: str = ''
    ) -> None:
        self.ip = ip
        self.user = user
        self.pwd = pwd

        self._login()

    def _login(self) -> None:
        try:
            self._si = SmartConnect(host=self.ip,
                                    user=self.user,
                                    pwd=self.pwd,
                                    disableSslCertValidation=True)
        except vim.fault.InvalidLogin as e:
            print(f"ERROR: {e.msg} Please set the correct username or password using the command below:")
            print(f"\tpython main.py config set --ip <HostIP> --user <username> --pwd <password>")
            sys.exit()
        except Exception as e:
            print(f"ERROR: {e}. Please set a valid VIM server using the command below:")
            print(f"\tpython main.py config set --ip <HostIP> --user <username> --pwd <password>")
            sys.exit()
        self._content = self._si.RetrieveContent()
        self.vim_obj = get_first_vim_obj(content=self._content,
                                         vim_type=vim.HostSystem)
        print(f"Connected to Host {self.ip}...")

    def datastore_manager(self):
        return DatastoreManager(self)

    def vm_manager(self):
        return VMManager(self)


class VMManager(QueryMixin[VM]):
    def __init__(self, esxi: ESXi) -> None:
        self.esxi = esxi

    def _list_all(self) -> List[VM]:
        return [VM(vm_vim_obj) for vm_vim_obj in self.esxi.vim_obj.vm]

    def create(self,
               name: str,
               datastore: vim.Datastore,
               annotation: str,
               memory_size: int,
               guest_id: str,
               num_cpus: int) -> VM:
        resource_pool_vim_obj = self.esxi.vim_obj.parent.resourcePool
        datacenter_vim_obj = get_first_vim_obj(self.esxi._content, vim.Datacenter)
        vm_folder_vim_obj = datacenter_vim_obj.vmFolder

        config_spec = create_config_spec(name, datastore, annotation, memory_size, guest_id, num_cpus)

        task = vm_folder_vim_obj.CreateVm(config_spec, resource_pool_vim_obj, self.esxi.vim_obj)
        WaitForTask(task)

        return VM(task.info.result)

    def delete(self, vm: VM) -> None:
        if format(vm.vim_obj.runtime.powerState) != "poweredOff":
            power_off_task = vm.vim_obj.PowerOffVM_Task()
            WaitForTask(power_off_task)

        vm_destroy_task = vm.vim_obj.Destroy()
        WaitForTask(vm_destroy_task)

    def add_scsi_controller(self, vm: VM):
        spec = vim.vm.ConfigSpec()
        scsi_ctr = vim.vm.device.VirtualDeviceSpec()
        scsi_ctr.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        scsi_ctr.device = vim.vm.device.ParaVirtualSCSIController()
        scsi_ctr.device.busNumber = 1
        scsi_ctr.device.hotAddRemove = True
        scsi_ctr.device.sharedBus = 'noSharing'
        scsi_ctr.device.scsiCtlrUnitNumber = 7
        spec.deviceChange = [scsi_ctr]
        task = vm.vim_obj.ReconfigVM_Task(spec=spec)
        WaitForTask(task)

    def import_ovf(self, name: str, datastore: Datastore, ovf_url: str):
        resource_pool_vim_obj = self.esxi.vim_obj.parent.resourcePool
        datacenter_vim_obj = get_first_vim_obj(self.esxi._content, vim.Datacenter)
        vm_folder_vim_obj = datacenter_vim_obj.vmFolder

        create_result = create_import_spec(content=self.esxi._content,
                                           ovf_url=ovf_url,
                                           resource_pool_vim_obj=resource_pool_vim_obj,
                                           datastore_vim_obj=datastore.vim_obj,
                                           vm_name=name)

        http_nfc_lease = create_http_nfc_lease(resource_pool_vim_obj=resource_pool_vim_obj,
                                               spec_vim_obj=create_result.importSpec,
                                               folder_vim_obj=vm_folder_vim_obj)

        deploy_vm_with_pull_mode(ovf_url, create_result, http_nfc_lease)

        http_nfc_lease.Complete()


class DatastoreManager(QueryMixin[Datastore]):
    def __init__(self, esxi: ESXi) -> None:
        self.esxi = esxi

    def _list_all(self) -> List[Datastore]:
        return [Datastore(datastore_vim_obj) for datastore_vim_obj in self.esxi.vim_obj.datastore]
