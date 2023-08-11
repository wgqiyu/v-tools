from enum import Enum
from typing import (
    List,
    Optional
)

from pyVmomi import vim

from vtools.query import by
from vtools.vsphere import find_device_option_by_type


class ScsiControllerType(Enum):
    LsiLogic = (vim.vm.device.VirtualLsiLogicController)
    ParaVirtualSCSI = (vim.vm.device.ParaVirtualSCSIController)
    BusLogic = (vim.vm.device.VirtualBusLogicController)
    LsiLogicSAS = (vim.vm.device.VirtualLsiLogicSASController)

    def __init__(self, clazz):
        self.vim_class = clazz


class ScsiBusSharingType(Enum):
    NoSharing = (
        vim.vm.device.VirtualSCSIController.Sharing.noSharing
    )
    VirtualSharing = (
        vim.vm.device.VirtualSCSIController.Sharing.virtualSharing
    )
    PhysicalSharing = (
        vim.vm.device.VirtualSCSIController.Sharing.physicalSharing
    )

    def __init__(self, value) -> None:
        self.vim_value = value


class DiskModeType(Enum):
    Persistent = (
        vim.vm.device.VirtualDiskOption.DiskMode.persistent
    )
    Nonpersistent = (
        vim.vm.device.VirtualDiskOption.DiskMode.nonpersistent
    )
    IndependentPersistent = (
        vim.vm.device.VirtualDiskOption.DiskMode.independent_persistent
    )
    IndependentNonpersistent = (
        vim.vm.device.VirtualDiskOption.DiskMode.independent_nonpersistent
    )

    def __init__(self, value) -> None:
        self.vim_value = value


class DiskBackingType:
    @staticmethod
    def flat_v2(
        thin: bool,
        eager: bool,
        disk_mode: DiskModeType = DiskModeType.Persistent,
        file_path: str = None,
        disk_uuid: str = None
    ) -> vim.vm.device.VirtualDevice.FileBackingInfo:
        disk_backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
        disk_backing.thinProvisioned = thin
        disk_backing.eagerlyScrub = eager
        disk_backing.diskMode = disk_mode.vim_value
        if file_path is not None:
            disk_backing.fileName = file_path
        if disk_uuid is not None:
            disk_backing.uuid = disk_uuid
        return disk_backing


class Device:
    def __init__(
        self,
        vim_obj: vim.vm.device.VirtualDevice,
        vm: 'VM'
    ) -> None:
        self.vim_obj = vim_obj
        self.vm = vm

    @property
    def name(self) -> str:
        return self.vim_obj.deviceInfo.label

    @property
    def key(self) -> str:
        return self.vim_obj.key


class Controller(Device):
    def __init__(
        self,
        vim_obj: vim.vm.device.VirtualController,
        vm: 'VM'
    ) -> None:
        super().__init__(vim_obj, vm)

    def __repr__(self):
        return f'Controller(vim_obj={self.vim_obj!r})'

    @property
    def next_free_unit(self) -> Optional[int]:
        device_option = find_device_option_by_type(
            self.vm.config_option, type(self.vim_obj)
        )
        max_devices = device_option.devices.max
        used_units = self._get_used_units()
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

    def _get_used_units(self) -> List[int]:
        used_units = []

        if isinstance(self.vim_obj, vim.vm.device.VirtualSCSIController):
            used_units.append(self.vim_obj.scsiCtlrUnitNumber)

        for device_vim_obj in self.vm.vim_obj.config.hardware.device:
            if device_vim_obj.key in self.vim_obj.device:
                used_units.append(device_vim_obj.unitNumber)
        return used_units


class Disk(Device):
    def __init__(
        self,
        vim_obj: vim.vm.device.VirtualDisk,
        vm: 'VM'
    ) -> None:
        super().__init__(vim_obj, vm)

    def __repr__(self):
        return f'Disk(vim_obj={self.vim_obj!r})'

    def __eq__(self, other):
        if isinstance(other, Disk):
            return self.key == other.key
        return False

    @property
    def size(self) -> str:
        return self.vim_obj.deviceInfo.summary

    @property
    def controller(self) -> Controller:
        controller_key = self.vim_obj.controllerKey
        return self.vm.controllers.get(
            by('key', lambda v: v == controller_key)
        )


class ScsiControllerCreateSpec:
    def __init__(self, controller_type: ScsiControllerType) -> None:
        self.controller_type = controller_type
        self.bus_sharing = ScsiBusSharingType.NoSharing

    def set_bus_sharing(self, value: ScsiBusSharingType) -> None:
        self.bus_sharing = value

    @property
    def vim_device_spec(self) -> vim.vm.device.VirtualDeviceSpec:
        new_device_spec = vim.vm.device.VirtualDeviceSpec()
        new_device_spec.operation = (
            vim.vm.device.VirtualDeviceSpec.Operation.add
        )

        new_controller = self.controller_type.vim_class()
        new_controller.sharedBus = self.bus_sharing.vim_value
        new_device_spec.device = new_controller

        return new_device_spec


class DiskCreateSpec:
    @property
    def vim_device_spec(self) -> vim.vm.device.VirtualDeviceSpec:
        new_device_spec = vim.vm.device.VirtualDeviceSpec()
        new_device_spec.operation = (
            vim.vm.device.VirtualDeviceSpec.Operation.add
        )

        new_controller = self.controller_type.vim_class()
        new_controller.sharedBus = self.bus_sharing.vim_value
        new_device_spec.device = new_controller

        return new_device_spec
