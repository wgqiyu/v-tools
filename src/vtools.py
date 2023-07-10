from typing import (
    Callable,
    List,
    Optional,
    Type
)

import requests

from pyVim.connect import SmartConnect
from pyVim.task import WaitForTask
from pyVmomi import vim


def list_vim_obj(
    content: vim.ServiceInstanceContent,
    vim_type: Type[vim.ManagedEntity],
    folder_vim_obj: vim.ManagedEntity = None,
    recurse: bool = True
) -> List[vim.ManagedEntity]:
    if not folder_vim_obj:
        folder_vim_obj = content.rootFolder

    types_in_view = [vim_type]
    container_view = content.viewManager.CreateContainerView(folder_vim_obj,
                                                             types_in_view,
                                                             recurse)
    vim_obj_list = list(container_view.view)
    container_view.Destroy()
    return vim_obj_list


def get_first_vim_obj(
    content: vim.ServiceInstanceContent,
    vim_type: Type[vim.ManagedEntity],
    folder_vim_obj: vim.ManagedEntity = None,
    recurse: bool = True
) -> Optional[vim.ManagedEntity]:
    vim_obj_list = list_vim_obj(content, vim_type, folder_vim_obj, recurse)
    if len(vim_obj_list) > 0:
        return vim_obj_list[0]
    return None


def get_vim_obj_by_name(
    content: vim.ServiceInstanceContent,
    vim_type: Type[vim.ManagedEntity],
    name: str,
    folder_vim_obj: vim.ManagedEntity = None,
    recurse: bool = True
) -> Optional[vim.ManagedEntity]:
    vim_obj_list = list_vim_obj(content, vim_type, folder_vim_obj, recurse)
    for vim_obj in vim_obj_list:
        if vim_obj.name == name:
            return vim_obj
    return None


def create_config_spec() -> vim.vm.ConfigSpec:
    config_spec = vim.vm.ConfigSpec()
    config_spec.annotation = 'Sample'
    config_spec.memoryMB = 128
    config_spec.guestId = 'otherGuest'
    config_spec.numCPUs = 1

    return config_spec


def create_import_spec(
    content: vim.ServiceInstanceContent,
    ovf_url: str,
    resource_pool_vim_obj: vim.ResourcePool,
    datastore_vim_obj: vim.Datastore,
    vm_name: str = None,
    disk_provisioning: str = None
) -> vim.OvfManager.CreateImportSpecResult:
    spec_params = vim.OvfManager.CreateImportSpecParams()
    if vm_name is not None:
        spec_params.entityName = vm_name
    if disk_provisioning is not None:
        spec_params.diskProvisioning = disk_provisioning
    spec_params.networkMapping = []

    network_mapping = vim.OvfManager.NetworkMapping()
    network_mapping.name = "VM Network"
    network_mapping.network = get_vim_obj_by_name(content=content,
                                                  vim_type=vim.Network,
                                                  name="VM Network")
    spec_params.networkMapping.append(network_mapping)

    response = requests.get(ovf_url)
    response.encoding = "utf-8"
    ovf_descriptor = response.text

    return content.ovfManager.CreateImportSpec(ovf_descriptor,
                                               resource_pool_vim_obj,
                                               datastore_vim_obj,
                                               spec_params)


class VM:
    def __init__(
        self,
        vim_obj: vim.VirtualMachine
    ) -> None:
        self.vim_obj = vim_obj

    @property
    def name(self) -> str:
        return self.vim_obj.summary.config.name

    def __repr__(self) -> str:
        return f'VM(name={self.name})'


class Datastore:
    def __init__(
        self,
        vim_obj: vim.Datastore
    ) -> None:
        self.vim_obj = vim_obj

    @property
    def name(self) -> str:
        return self.vim_obj.summary.name

    @property
    def type(self) -> str:
        return self.vim_obj.summary.type

    def __repr__(self):
        return f'Datastore(name="{self.name}", type="{self.type}")'


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
        self._si = SmartConnect(host=self.ip,
                                user=self.user,
                                pwd=self.pwd,
                                disableSslCertValidation=True)
        self._content = self._si.RetrieveContent()
        self.vim_obj = get_first_vim_obj(content=self._content,
                                         vim_type=vim.HostSystem)

    def create_vm(self, name: str, datastore: Datastore) -> VM:
        resource_pool_vim_obj = self.vim_obj.parent.resourcePool
        datacenter_vim_obj = get_first_vim_obj(self._content, vim.Datacenter)
        vm_folder_vim_obj = datacenter_vim_obj.vmFolder

        config_spec = create_config_spec()
        config_spec.name = name
        files = vim.vm.FileInfo()
        files.vmPathName = f"[{datastore.name}]"
        config_spec.files = files

        task = vm_folder_vim_obj.CreateVm(config_spec, resource_pool_vim_obj,
                                          self.vim_obj)
        WaitForTask(task)

        return VM(task.info.result)

    def list_vm(self, condition: Callable[[VM], bool] = None) -> List[VM]:
        all_vms = [VM(vm_vim_obj) for vm_vim_obj in
                   list_vim_obj(self._content, vim.VirtualMachine)]

        if condition is None:
            return all_vms

        return [one_vm for one_vm in all_vms if condition(one_vm)]

    def get_vm(self, condition: Callable[[VM], bool] = None) -> VM:
        for one_vm in self.list_vm():
            if condition(one_vm):
                return one_vm
        return None

    def delete_vm(self, vm: VM) -> None:
        if format(vm.vim_obj.runtime.powerState) != "poweredOff":
            power_off_task = vm.vim_obj.PowerOffVM_Task()
            WaitForTask(power_off_task)

        vm_destroy_task = vm.vim_obj.Destroy()
        WaitForTask(vm_destroy_task)

    def list_datastore(self, condition: Callable[[Datastore], bool] = None) -> List[Datastore]:
        all_datastores = [Datastore(datastore_vim_obj) for datastore_vim_obj in
                          list_vim_obj(self._content, vim.Datastore)]

        if condition is None:
            return all_datastores

        return [one_datastore for one_datastore in all_datastores
                if condition(one_datastore)]

    def get_datastore(self, condition: Callable[[Datastore], bool] = None) -> Datastore:
        for one_datastore in self.list_datastore():
            if condition(one_datastore):
                return one_datastore
        return None
