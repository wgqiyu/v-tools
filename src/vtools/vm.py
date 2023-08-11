import copy
from enum import Enum
from functools import cached_property
from typing import List

from loguru import logger
from pyVim.task import WaitForTask
from pyVmomi import vim
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    TryAgain
)

from vtools.datastore import Datastore
from vtools.device import (
    Controller,
    Disk,
    ScsiControllerCreateSpec,
    ScsiControllerType,
    ScsiBusSharingType
)
from vtools.exception import InvalidStateError
from vtools.query import QueryMixin
from vtools.snapshot import (
    Snapshot,
    SnapshotType,
    flatten_snapshot_tree,
    find_snapshot_tree
)
from vtools.vsphere import (
    get_first_vim_obj,
    create_http_nfc_lease,
    deploy_vm_with_pull_mode,
    create_import_spec,
    find_device_option_by_type
)


class FirmwareType(Enum):
    BIOS = (vim.vm.GuestOsDescriptor.FirmwareType.bios)
    EFI = (vim.vm.GuestOsDescriptor.FirmwareType.efi)

    def __init__(self, value) -> None:
        self.vim_value = value


class VM:
    def __init__(self, vim_obj: vim.VirtualMachine) -> None:
        self.vim_obj = vim_obj

    def __repr__(self) -> str:
        return f'VM(vim_obj={self.vim_obj!r})'

    @property
    def name(self) -> str:
        return self.vim_obj.summary.config.name

    @property
    def primary_ip(self) -> str:
        return self.vim_obj.guest.ipAddress

    @property
    def ips(self) -> List[str]:
        return [
            nic_ip.ipAddress
            for nic_info in self.vim_obj.guest.net
            for nic_ip in nic_info.ipConfig.ipAddress
        ]

    @property
    def path(self) -> str:
        return self.vim_obj.summary.config.vmPathName

    @property
    def power_state(self) -> vim.VirtualMachine.PowerState:
        return self.vim_obj.summary.runtime.powerState

    @property
    def hardware_version(self) -> str:
        return self.vim_obj.config.version

    @property
    def esxi(self) -> 'ESXi':
        from vtools.esxi import ESXi
        return ESXi(vim_obj=self.vim_obj.runtime.host)

    @cached_property
    def config_option(self) -> vim.vm.ConfigOption:
        return self.esxi.get_vm_config_option(self.hardware_version)

    @cached_property
    def cpu(self) -> 'CpuManager':
        return CpuManager(self)

    @cached_property
    def memory(self) -> 'MemoryManager':
        return MemoryManager(self)

    @cached_property
    def scsi_controllers(self) -> 'ScsiControllerManager':
        return ScsiControllerManager(self)

    @cached_property
    def disks(self) -> 'DiskManager':
        return DiskManager(self)

    @cached_property
    def snapshots(self) -> 'SnapshotManager':
        return SnapshotManager(self)

    def power_on(self) -> None:
        self._invoke_power_on()
        self._wait_until_power_state_is(vim.VirtualMachine.PowerState.poweredOn)

    def power_off(self) -> None:
        self._invoke_power_off()
        self._wait_until_power_state_is(
            vim.VirtualMachine.PowerState.poweredOff)

    def suspend(self) -> None:
        self._invoke_suspend()
        self._wait_until_power_state_is(vim.VirtualMachine.PowerState.suspended)

    def revert_to_snapshot(self, snapshot: Snapshot) -> None:
        if snapshot.vim_obj.vm != self.vim_obj:
            raise InvalidStateError()

        WaitForTask(snapshot.vim_obj.Revert(suppressPowerOn=False))

    @retry(stop=stop_after_attempt(12),
           wait=wait_fixed(5))
    def _invoke_power_on(self) -> None:
        if self.power_state == vim.VirtualMachine.PowerState.poweredOn:
            logger.warning(
                "PowerState was already PoweredOn, no need to power on"
            )
            return
        WaitForTask(self.vim_obj.PowerOn())

    @retry(stop=stop_after_attempt(12),
           wait=wait_fixed(5))
    def _invoke_power_off(self) -> None:
        if self.power_state == vim.VirtualMachine.PowerState.poweredOff:
            logger.warning(
                "PowerState was already PoweredOff, no need to power off"
            )
            return
        WaitForTask(self.vim_obj.PowerOff())

    @retry(stop=stop_after_attempt(12),
           wait=wait_fixed(5))
    def _invoke_suspend(self) -> None:
        if self.power_state == vim.VirtualMachine.PowerState.suspended:
            logger.warning(
                "PowerState was already Suspended, no need to suspend"
            )
            return
        WaitForTask(self.vim_obj.Suspend())

    @retry(stop=stop_after_attempt(60),
           wait=wait_fixed(10))
    def _wait_until_power_state_is(
        self,
        expected_state: vim.VirtualMachine.PowerState
    ) -> None:
        current_power_state = self.power_state
        if current_power_state != expected_state:
            logger.warning(f"PowerStatus was still not {expected_state}: "
                           f"{current_power_state}")
            raise TryAgain
        else:
            logger.info(f"PowerStatus was {expected_state}")


class CpuManager:
    def __init__(self, vm: VM) -> None:
        self.vm = vm

    @property
    def number(self) -> int:
        return self.vm.vim_obj.config.hardware.numCPU

    @number.setter
    def number(self, value) -> None:
        if self.vm.power_state != vim.VirtualMachine.PowerState.poweredOff:
            raise InvalidStateError()

        config_spec = vim.vm.ConfigSpec()
        config_spec.numCPUs = value

        WaitForTask(self.vm.vim_obj.Reconfigure(config_spec))

    @property
    def cores_per_socket(self) -> int:
        return self.vm.vim_obj.config.hardware.numCoresPerSocket

    @cores_per_socket.setter
    def cores_per_socket(self, value) -> None:
        if self.vm.power_state != vim.VirtualMachine.PowerState.poweredOff:
            raise InvalidStateError()

        config_spec = vim.vm.ConfigSpec()
        config_spec.numCoresPerSocket = value

        WaitForTask(self.vm.vim_obj.Reconfigure(config_spec))


class MemoryManager:
    def __init__(self, vm: VM) -> None:
        self.vm = vm

    @property
    def size_in_mb(self) -> int:
        return self.vm.vim_obj.config.hardware.memoryMB

    @size_in_mb.setter
    def size_in_mb(self, value) -> None:
        if self.vm.power_state != vim.VirtualMachine.PowerState.poweredOff:
            raise InvalidStateError()

        config_spec = vim.vm.ConfigSpec()
        config_spec.memoryMB = value

        WaitForTask(self.vm.vim_obj.Reconfigure(config_spec))


class ScsiControllerManager(QueryMixin[Controller]):
    def __init__(self, vm: VM) -> None:
        self.vm = vm

    def _list_all(self) -> List[Controller]:
        return [Controller(device_vim_obj, self.vm) for device_vim_obj
                in self.vm.vim_obj.config.hardware.device
                if
                isinstance(device_vim_obj, vim.vm.device.VirtualSCSIController)]

    def add(self, spec: ScsiControllerCreateSpec) -> None:
        existing_scsi_controllers = self.list()

        new_controller_spec = spec.vim_device_spec
        new_controller_spec.device.key = -1
        new_controller_spec.device.busNumber = len(
            existing_scsi_controllers) + 1

        config_spec = vim.vm.ConfigSpec()
        config_spec.deviceChange = [new_controller_spec]

        WaitForTask(self.vm.vim_obj.Reconfigure(config_spec))


class DiskManager(QueryMixin[Disk]):
    def __init__(self, vm: VM) -> None:
        self.vm = vm

    def _list_all(self) -> List[Disk]:
        return [Disk(device_vim_obj, self.vm) for device_vim_obj
                in self.vm.vim_obj.config.hardware.device
                if isinstance(device_vim_obj, vim.vm.device.VirtualDisk)]

    def add(
        self,
        size_in_mb: int,
        backing: vim.vm.device.VirtualDevice.FileBackingInfo,
        controller: Controller
    ) -> Disk:
        existing_disks = self.list()

        new_disk = vim.vm.device.VirtualDisk()
        new_disk.key = -1
        new_disk.controllerKey = controller.key
        new_disk.unitNumber = controller.next_free_unit
        new_disk.backing = backing
        new_disk.capacityInKB = size_in_mb * 1024

        new_disk_spec = vim.vm.device.VirtualDeviceSpec()
        new_disk_spec.operation = (
            vim.vm.device.VirtualDeviceSpec.Operation.add
        )
        new_disk_spec.fileOperation = (
            vim.vm.device.VirtualDeviceSpec.FileOperation.create
        )

        new_disk_spec.device = new_disk

        config_spec = vim.vm.ConfigSpec()
        config_spec.deviceChange = [new_disk_spec]

        WaitForTask(self.vm.vim_obj.Reconfigure(config_spec))

        new_disks = [disk for disk in self.list() if disk not in existing_disks]
        return new_disks[0]

    def remove(self, disk: Disk) -> None:
        remove_disk_spec = vim.vm.device.VirtualDeviceSpec()
        remove_disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
        remove_disk_spec.device = disk.vim_obj

        config_spec = vim.vm.ConfigSpec()
        config_spec.deviceChange = [remove_disk_spec]

        WaitForTask(self.vm.vim_obj.Reconfigure(config_spec))


class SnapshotManager(QueryMixin[Snapshot]):
    def __init__(self, vm: VM) -> None:
        self.vm = vm

    def _list_all(self) -> List[Snapshot]:
        snapshot_info = self.vm.vim_obj.snapshot
        if snapshot_info is None:
            return []

        snapshot_tree_list = []
        flatten_snapshot_tree(snapshot_info.rootSnapshotList,
                              snapshot_tree_list)

        return [Snapshot(snapshot_tree.snapshot, snapshot_tree)
                for snapshot_tree in snapshot_tree_list]

    def create(
        self,
        name: str,
        snapshot_type: SnapshotType,
        description: str = None
    ) -> Snapshot:
        task = self.vm.vim_obj.CreateSnapshot(
            name, description if description else name,
            snapshot_type.is_memory,
            snapshot_type.is_quiesced
        )
        WaitForTask(task)
        new_snapshot_vim_obj = task.info.result
        new_snapshot_tree_vim_obj = find_snapshot_tree(
            self.vm.vim_obj.snapshot.rootSnapshotList,
            new_snapshot_vim_obj
        )
        return Snapshot(new_snapshot_vim_obj, new_snapshot_tree_vim_obj)

    def delete(self, snapshot: Snapshot) -> None:
        if snapshot.vim_obj.vm != self.vm.vim_obj:
            raise InvalidStateError()

        WaitForTask(snapshot.vim_obj.Remove(False))


class CreateVMSpec:
    def __init__(self, config_option: vim.vm.ConfigOption) -> None:
        self.config_option = config_option

        self.firmware = None

        self.cpu_count = 1
        self.cpu_cores_per_socket = 1
        self.cpu_hot_add_enabled = False
        self.cpu_hot_remove_enabled = False

        self.memory_size_in_mb = 128
        self.memory_hot_add_enabled = False

        self.guest_id = "otherGuest"

        self.devices = []
        self._last_used_key = 0
        self._last_used_scsi_bus = 0

    @property
    def vim_config_spec(self) -> vim.vm.ConfigSpec:
        spec = vim.vm.ConfigSpec()

        spec.firmware = self.firmware

        spec.numCPUs = self.cpu_count
        spec.numCoresPerSocket = self.cpu_cores_per_socket

        spec.memoryMB = self.memory_size_in_mb

        spec.guestId = self.guest_id

        spec.version = self.config_option.version

        spec.deviceChange = copy.deepcopy(self.devices)

        return spec

    def set_boot(
        self,
        firmware: FirmwareType
    ) -> None:
        self.firmware = firmware.vim_value

    def set_cpu(
        self,
        number: int = 1,
        cores_per_socket: int = 1,
    ) -> None:
        self.cpu_count = number
        self.cpu_cores_per_socket = cores_per_socket

    def set_memory(
        self,
        size_in_mb: int = 128
    ) -> None:
        self.memory_size_in_mb = size_in_mb

    def set_guest(
        self,
        id: str = "otherGuest"
    ) -> None:
        self.guest_id = id

    def add_scsi_controller(
        self,
        type: ScsiControllerType,
        bus_sharing: ScsiBusSharingType
    ) -> vim.vm.device.VirtualSCSIController:
        new_controller = type.vim_class()
        new_controller.sharedBus = bus_sharing.vim_value
        new_controller.key = self._get_next_free_key()
        new_controller.busNumber = self._get_next_free_scsi_bus()

        self._add_device(new_controller)

        return new_controller

    def add_disk(
        self,
        size_in_mb: int,
        backing: vim.vm.device.VirtualDevice.BackingInfo,
        controller: vim.vm.device.VirtualController
    ) -> vim.vm.device.VirtualDisk:
        new_disk = vim.vm.device.VirtualDisk()
        new_disk.key = self._get_next_free_key()
        new_disk.controllerKey = controller.key
        new_disk.unitNumber = self._get_next_free_unit(controller)
        new_disk.backing = backing
        new_disk.capacityInKB = size_in_mb * 1024

        self._add_device(new_disk)

        return new_disk

    def create_vm(self, name: str, esxi: 'ESXi', datastore: Datastore) -> VM:
        resource_pool_vim_obj = esxi.vim_obj.parent.resourcePool
        datacenter_vim_obj = get_first_vim_obj(esxi._content, vim.Datacenter)
        vm_folder_vim_obj = datacenter_vim_obj.vmFolder

        config_spec = self.vim_config_spec
        config_spec.name = name

        files = vim.vm.FileInfo()
        files.vmPathName = f"[{datastore.name}]"
        config_spec.files = files

        for one_change in config_spec.deviceChange:
            device_backing = one_change.device.backing
            if (
                device_backing is not None
                and
                isinstance(
                    device_backing,
                    vim.vm.device.VirtualDevice.FileBackingInfo
                )
            ):
                if (
                    not device_backing.fileName
                    or
                    device_backing.fileName.isspace()
                ):
                    device_backing.fileName = f"[{datastore.name}]"

        task = vm_folder_vim_obj.CreateVm(config_spec, resource_pool_vim_obj,
                                          esxi.vim_obj)
        return VM(task.info.result)

    def _add_device(self, device: vim.vm.device.VirtualDevice) -> None:
        new_device_spec = vim.vm.device.VirtualDeviceSpec()
        new_device_spec.operation = (
            vim.vm.device.VirtualDeviceSpec.Operation.add
        )

        if (
            device.backing is not None
            and
            isinstance(
                device.backing,
                vim.vm.device.VirtualDevice.FileBackingInfo
            )
        ):
            new_device_spec.fileOperation = (
                vim.vm.device.VirtualDeviceSpec.FileOperation.create
            )

        new_device_spec.device = device
        self.devices.append(new_device_spec)

    def _get_next_free_key(self) -> int:
        self._last_used_key = self._last_used_key - 1
        return self._last_used_key

    def _get_next_free_scsi_bus(self) -> int:
        self._last_used_scsi_bus = self._last_used_scsi_bus + 1
        return self._last_used_scsi_bus

    def _find_device_option(self, device_type):
        self.config_option

    def _get_used_units(
        self,
        controller: vim.vm.device.VirtualController
    ) -> List[int]:
        used_units = []
        for device_spec in self.devices:
            device = device_spec.device
            if (isinstance(device, vim.vm.device.VirtualSCSIController) and
                device.key == controller.key):
                if device.scsiCtlrUnitNumber is not None:
                    used_units.append(device.scsiCtlrUnitNumber)
                else:
                    scsi_controller_option = find_device_option_by_type(
                        self.config_option,
                        type(controller)
                    )
                    used_units.append(
                        scsi_controller_option.scsiCtlrUnitNumber
                    )
                continue
            if device.controllerKey != controller.key:
                continue
            used_units.append(device.unitNumber)
        return used_units

    def _get_next_free_unit(
        self,
        controller: vim.vm.device.VirtualController
    ) -> int:
        device_option = find_device_option_by_type(
            self.config_option, type(controller)
        )
        max_devices = device_option.devices.max
        used_units = self._get_used_units(controller)
        if len(used_units) >= max_devices:
            return None

        used_units.sort()
        last_index = len(used_units) - 1
        if used_units[last_index] == last_index:
            return last_index + 1

        index = 0
        while used_units[index] == index:
            index = index + 1
        return index


class OvfImportSpec:
    def __init__(self, ovf_url: str) -> None:
        self.ovf_url = ovf_url

    def create_vm(self, name: str, esxi: 'ESXi', datastore: Datastore) -> VM:
        resource_pool_vim_obj = esxi.vim_obj.parent.resourcePool
        datacenter_vim_obj = get_first_vim_obj(esxi._content, vim.Datacenter)
        vm_folder_vim_obj = datacenter_vim_obj.vmFolder

        create_result = create_import_spec(content=esxi._content,
                                           ovf_url=self.ovf_url,
                                           resource_pool_vim_obj=resource_pool_vim_obj,
                                           datastore_vim_obj=datastore.vim_obj,
                                           vm_name=name)

        http_nfc_lease = create_http_nfc_lease(
            resource_pool_vim_obj=resource_pool_vim_obj,
            spec_vim_obj=create_result.importSpec,
            folder_vim_obj=vm_folder_vim_obj)

        task = deploy_vm_with_pull_mode(self.ovf_url, create_result,
                                        http_nfc_lease)
        http_nfc_lease.Complete()
        return VM(task.info.result)


def from_scratch(config_option: vim.vm.ConfigOption) -> CreateVMSpec:
    return CreateVMSpec(config_option)


def from_ovf(ovf_url: str) -> OvfImportSpec:
    return OvfImportSpec(ovf_url)
