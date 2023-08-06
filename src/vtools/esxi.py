import sys
from typing import (
    List
)

from pyVim.connect import SmartConnect
from pyVmomi import vim

from vtools.exception import handle_exceptions
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

    @handle_exceptions()
    def _login(self) -> None:
        self._si = SmartConnect(host=self.ip,
                                user=self.user,
                                pwd=self.pwd,
                                disableSslCertValidation=True)
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

    def edit(self,
             vm: VM,
             new_name: str,
             datastore: vim.Datastore,
             annotation: str,
             memory_size: int,
             guest_id: str,
             num_cpus: int) -> VM:
        if vm.power_state != "poweredOff":
            print(f"The current state of the VM is {vm.power_state}, please turn off the VM to edit it.")
            sys.exit()
        config_spec = create_config_spec(new_name, datastore, annotation, memory_size, guest_id, num_cpus)
        task = vm.vim_obj.Reconfigure(config_spec)
        WaitForTask(task)

        new_vm_obj = self.get(lambda _: _.name == new_name) if new_name else self.get(lambda _: _.name == vm.name)

        return new_vm_obj

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

    def remove_scsi_controller(self, vm: VM, disk_num: int, disk_prefix_label='SCSI controller '):
        disk_label = disk_prefix_label + str(disk_num)
        # Find the disk device
        virtual_disk_device = None
        for device in vm.vim_obj.config.hardware.device:
            if isinstance(device, vim.vm.device.ParaVirtualSCSIController) and device.deviceInfo.label == disk_label:
                virtual_disk_device = device
        if not virtual_disk_device:
            print(f"Virtual {disk_label} could not be found.")
            sys.exit()
        spec = vim.vm.ConfigSpec()
        disk_spec = vim.vm.device.VirtualDeviceSpec()
        disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
        disk_spec.device = virtual_disk_device
        dev_changes = [disk_spec]
        spec.deviceChange = dev_changes
        WaitForTask(vm.vim_obj.ReconfigVM_Task(spec=spec))

    @handle_exceptions()
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

        return self.get(lambda vm: vm.name == name)


class DatastoreManager(QueryMixin[Datastore]):
    def __init__(self, esxi: ESXi) -> None:
        self.esxi = esxi

    def _list_all(self) -> List[Datastore]:
        return [Datastore(datastore_vim_obj) for datastore_vim_obj in self.esxi.vim_obj.datastore]
