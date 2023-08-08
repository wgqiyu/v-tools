from typing import (
    List,
    Optional,
    Type
)

from pyVmomi import vim
from pyVmomi.VmomiSupport import ManagedObject

from vtools.cli.exception import handle_exceptions
from vtools.snapshot import Snapshot
from pyVim.task import WaitForTask

import requests
from requests.compat import urljoin
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    TryAgain
)


def list_vim_obj(
    content: vim.ServiceInstanceContent,
    vim_type: Type[vim.ManagedEntity],
    container_vim_obj: vim.ManagedEntity = None,
    recurse: bool = True
) -> List[ManagedObject]:
    if not container_vim_obj:
        container_vim_obj = content.rootFolder

    types_in_view = [vim_type]
    container_view = content.viewManager.CreateContainerView(container_vim_obj,
                                                             types_in_view,
                                                             recurse)
    vim_obj_list = list(container_view.view)
    container_view.Destroy()
    return vim_obj_list


def get_first_vim_obj(
    content: vim.ServiceInstanceContent,
    vim_type: Type[vim.ManagedEntity],
    container_vim_obj: vim.ManagedEntity = None,
    recurse: bool = True
) -> Optional[ManagedObject]:
    vim_obj_list = list_vim_obj(content, vim_type, container_vim_obj, recurse)
    if len(vim_obj_list) > 0:
        return vim_obj_list[0]
    return None


def get_vim_obj_by_name(
    content: vim.ServiceInstanceContent,
    vim_type: Type[vim.ManagedEntity],
    name: str,
    container_vim_obj: vim.ManagedEntity = None,
    recurse: bool = True
) -> Optional[ManagedObject]:
    vim_obj_list = list_vim_obj(content, vim_type, container_vim_obj, recurse)
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


def create_disk_spec(controller: vim.vm.device.VirtualSCSIController,
                     unit_number: int,
                     disk_size: int,
                     disk_type: str) -> vim.vm.device.VirtualDeviceSpec:
    spec = vim.vm.ConfigSpec()
    disk_in_kb = int(disk_size) * 1024 * 1024
    disk_spec = vim.vm.device.VirtualDeviceSpec()
    disk_spec.fileOperation = "create"
    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
    disk_spec.device = vim.vm.device.VirtualDisk()
    disk_spec.device.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
    if disk_type == 'thin':
        disk_spec.device.backing.thinProvisioned = True
    disk_spec.device.backing.diskMode = 'persistent'
    disk_spec.device.capacityInKB = disk_in_kb
    disk_spec.device.unitNumber = unit_number
    disk_spec.device.controllerKey = controller.key
    spec.deviceChange = [disk_spec]
    return spec


def remove_disk_spec(virtual_disk_device: vim.vm.device.VirtualDisk):
    spec = vim.vm.ConfigSpec()
    disk_spec = vim.vm.device.VirtualDeviceSpec()
    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
    disk_spec.device = virtual_disk_device
    dev_changes = [disk_spec]
    spec.deviceChange = dev_changes
    return spec


def create_controller_spec(bus_number: int):
    spec = vim.vm.ConfigSpec()
    scsi_ctr = vim.vm.device.VirtualDeviceSpec()
    scsi_ctr.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
    scsi_ctr.device = vim.vm.device.ParaVirtualSCSIController()
    scsi_ctr.device.busNumber = bus_number
    scsi_ctr.device.hotAddRemove = True
    scsi_ctr.device.sharedBus = 'noSharing'
    scsi_ctr.device.scsiCtlrUnitNumber = 7
    spec.deviceChange = [scsi_ctr]
    return spec


def remove_controller_spec(virtual_disk_device: vim.vm.device.ParaVirtualSCSIController):
    spec = vim.vm.ConfigSpec()
    disk_spec = vim.vm.device.VirtualDeviceSpec()
    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
    disk_spec.device = virtual_disk_device
    dev_changes = [disk_spec]
    spec.deviceChange = dev_changes
    return spec


def list_snapshots_recursively(snapshot_data, snapshots):
    if snapshots is not None:
        for snapshot in snapshots:
            snapshot_data.append(Snapshot(snapshot))
            list_snapshots_recursively(snapshot_data, snapshot.childSnapshotList)
    return snapshot_data


@handle_exceptions
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
