from typing import (
    Callable,
    List,
    Optional,
    Type
)

import requests
from requests.compat import urljoin
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    TryAgain
)

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


def create_config_spec(name: str,
                       datastore: vim.Datastore,
                       annotation: str,
                       memory_size: int,
                       guest_id: str,
                       num_cpus: int) -> vim.vm.ConfigSpec:
    config_spec = vim.vm.ConfigSpec()
    config_spec.annotation = annotation
    config_spec.memoryMB = memory_size
    config_spec.guestId = guest_id
    config_spec.numCPUs = num_cpus
    config_spec.name = name
    files = vim.vm.FileInfo()
    files.vmPathName = f"[{datastore.name}]"
    config_spec.files = files

    return config_spec


def create_import_spec(
    content: vim.ServiceInstanceContent,
    ovf_url: str,
    resource_pool_vim_obj: vim.ResourcePool,
    datastore_vim_obj: vim.Datastore,
    vm_name: str = None,
    disk_provisioning: str = None
) -> vim.OvfManager.CreateImportSpecResult:
    response = requests.get(ovf_url)
    response.encoding = "utf-8"
    ovf_descriptor = response.text

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

    return content.ovfManager.CreateImportSpec(ovf_descriptor,
                                               resource_pool_vim_obj,
                                               datastore_vim_obj,
                                               spec_params)


def create_http_nfc_lease(resource_pool_vim_obj: vim.ResourcePool,
                          spec_vim_obj: vim.ImportSpec,
                          folder_vim_obj: vim.Folder) -> vim.HttpNfcLease:
    http_nfc_lease = resource_pool_vim_obj.ImportVApp(spec_vim_obj, folder_vim_obj)

    @retry(stop=stop_after_attempt(6),
           wait=wait_fixed(5))
    def wait_until_http_nfc_lease_ready():
        lease_state = http_nfc_lease.state
        if lease_state != vim.HttpNfcLease.State.ready:
            raise TryAgain

    wait_until_http_nfc_lease_ready()

    return http_nfc_lease


def deploy_vm_with_pull_mode(ovf_url, import_spec, http_nfc_lease):
    source_files = []
    for file in import_spec.fileItem:
        source_file = vim.HttpNfcLease.SourceFile(
            targetDeviceId=file.deviceId,
            url=urljoin(ovf_url, file.path),
            sslThumbprint="",
            create=file.create
        )
        source_files.append(source_file)
    task = http_nfc_lease.PullFromUrls(source_files)
    WaitForTask(task)


def list_snapshots_recursively(snapshot_data, snapshots):
    if snapshots is not None:
        for snapshot in snapshots:
            snapshot_data.append(Snapshot(snapshot))
            list_snapshots_recursively(snapshot_data, snapshot.childSnapshotList)
    return snapshot_data


class VM:
    def __init__(
        self,
        vim_obj: vim.VirtualMachine
    ) -> None:
        self.vim_obj = vim_obj

    @property
    def name(self) -> str:
        return self.vim_obj.summary.config.name

    @property
    def path(self) -> str:
        return self.vim_obj.summary.config.vmPathName

    @property
    def power_state(self) -> str:
        return self.vim_obj.summary.runtime.powerState

    @property
    def memory(self) -> int:
        return self.vim_obj.summary.config.memorySizeMB

    @property
    def num_cpus(self) -> int:
        return self.vim_obj.summary.config.numCpu

    def __repr__(self) -> str:
        return f'VM(name={self.name}, path={self.path}, memory={self.memory}, num_cpus={self.num_cpus})'

    def power_on(self):
        WaitForTask(self.vim_obj.PowerOn())

    def power_off(self):
        WaitForTask(self.vim_obj.PowerOff())

    def suspend(self):
        WaitForTask(self.vim_obj.Suspend())

    def list_snapshot(self):
        snapshot_data = []
        snapshot = self.vim_obj.snapshot
        # print("rootSnapshotList", snapshot.rootSnapshotList)
        if snapshot is not None:
            list_snapshots_recursively(snapshot_data, snapshot.rootSnapshotList)
            return snapshot_data
        else:
            print(f"There is no snapshots yet on {self.name}")
            return snapshot_data

    def get_snapshot(self, name: str):
        snapshots = self.list_snapshot()
        for snapshot in snapshots:
            if snapshot.name == name:
                return snapshot
        return None

    def create_snapshot(self, name: str,
                        description: str = None,
                        memory: bool = True,
                        quiesce: bool = False):
        if self.get_snapshot(name):
            print("Invalid Name: The VM has already exist. ")
            return
        task = self.vim_obj.CreateSnapshot(name, description, memory, quiesce)
        WaitForTask(task)
        snapshot = self.get_snapshot(name)
        return Snapshot(snapshot)

    def destroy_snapshot(self, name: str):
        snapshot = self.get_snapshot(name)
        if snapshot is not None:
            snapshot.remove()
            return name
        else:
            print("The VM you designated does not exist")


class Snapshot:
    def __init__(self, vim_obj: vim.vm.SnapshotTree) -> None:
        self.vim_obj = vim_obj

    @property
    def name(self) -> str:
        return self.vim_obj.name

    @property
    def description(self) -> str:
        return self.vim_obj.description

    def __repr__(self):
        return f'Snapshot(name={self.name}, description={self.description})'

    def remove(self):
        task = self.vim_obj.snapshot.Remove(removeChildren=False)
        WaitForTask(task)


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

    def create_vm(self,
                  name: str,
                  datastore: vim.Datastore,
                  annotation: str,
                  memory_size: int,
                  guest_id: str,
                  num_cpus: int) -> VM:
        resource_pool_vim_obj = self.vim_obj.parent.resourcePool
        datacenter_vim_obj = get_first_vim_obj(self._content, vim.Datacenter)
        vm_folder_vim_obj = datacenter_vim_obj.vmFolder

        config_spec = create_config_spec(name, datastore, annotation, memory_size, guest_id, num_cpus)

        task = vm_folder_vim_obj.CreateVm(config_spec, resource_pool_vim_obj,
                                          self.vim_obj)
        WaitForTask(task)

        return VM(task.info.result)

    def import_ovf(self, name: str, datastore: Datastore, ovf_url: str) -> VM:
        resource_pool_vim_obj = self.vim_obj.parent.resourcePool
        datacenter_vim_obj = get_first_vim_obj(self._content, vim.Datacenter)
        vm_folder_vim_obj = datacenter_vim_obj.vmFolder

        create_result = create_import_spec(content=self._content,
                                           ovf_url=ovf_url,
                                           resource_pool_vim_obj=resource_pool_vim_obj,
                                           datastore_vim_obj=datastore.vim_obj,
                                           vm_name=name)

        http_nfc_lease = create_http_nfc_lease(resource_pool_vim_obj=resource_pool_vim_obj,
                                               spec_vim_obj=create_result.importSpec,
                                               folder_vim_obj=vm_folder_vim_obj)

        deploy_vm_with_pull_mode(ovf_url, create_result, http_nfc_lease)

        http_nfc_lease.Complete()

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
