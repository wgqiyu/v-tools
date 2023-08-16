from typing import (
    List,
    Optional,
    Type
)

import requests
from pyVim.task import WaitForTask
from pyVmomi import vim
from pyVmomi.VmomiSupport import ManagedObject
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


def find_device_option_by_type(
    config_option: vim.vm.ConfigOption,
    device_type: Type[vim.vm.device.VirtualDevice]
) -> vim.vm.device.VirtualDeviceOption:
    for device_option in config_option.hardwareOptions.virtualDeviceOption:
        if device_option.type == device_type:
            return device_option
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
    http_nfc_lease = resource_pool_vim_obj.ImportVApp(spec_vim_obj,
                                                      folder_vim_obj)

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
    return task
