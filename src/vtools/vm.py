import sys
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

from vtools.device import Controller, Disk
from vtools.exception import InvalidStateError
from vtools.query import QueryMixin
from vtools.snapshot import Snapshot
from vtools.vsphere import list_snapshots_recursively


class VM:
    def __init__(
        self,
        vim_obj: vim.VirtualMachine
    ) -> None:
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
    def controllers(self) -> 'ControllerManager':
        return ControllerManager(self)

    @cached_property
    def disks(self) -> 'DiskManager':
        return DiskManager(self)

    def power_on(self) -> None:
        self._invoke_power_on()
        self._wait_until_power_state_is(vim.VirtualMachine.PowerState.poweredOn)

    def power_off(self) -> None:
        self._invoke_power_off()
        self._wait_until_power_state_is(vim.VirtualMachine.PowerState.poweredOff)

    def suspend(self):
        self._invoke_suspend()
        self._wait_until_power_state_is(vim.VirtualMachine.PowerState.suspended)

    def snapshot_manager(self):
        return SnapshotManager(self)

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
        return self.vm.vim_obj.config.numCoresPerSocket

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


class ControllerManager(QueryMixin[Controller]):
    def __init__(self, vm: VM) -> None:
        self.vm = vm

    def _list_all(self) -> List[Controller]:
        return [Controller(device_vim_obj, self.vm) for device_vim_obj
                in self.vm.vim_obj.config.hardware.device
                if isinstance(device_vim_obj, vim.vm.device.VirtualController)]


class SnapshotManager(QueryMixin[Snapshot]):
    def __init__(self, vm_obj: VM) -> None:
        self.vm_obj = vm_obj

    def _list_all(self) -> List[Snapshot]:
        snapshot_data = []
        snapshot = self.vm_obj.vim_obj.snapshot
        if snapshot is not None:
            list_snapshots_recursively(snapshot_data, snapshot.rootSnapshotList)
            return snapshot_data
        else:
            return snapshot_data

    def create_snapshot(self, name: str,
                        description: str = None,
                        memory: bool = True,
                        quiesce: bool = False):
        if [vm_obj for vm_obj in self.vm_obj.snapshot_manager().list() if vm_obj.vim_obj.name == name]:
            print(f"Invalid Name: The VM snapshot name {name} has already exist. ")
            sys.exit()
        task = self.vm_obj.vim_obj.CreateSnapshot(name, description, memory, quiesce)
        WaitForTask(task)
        snapshot = self.vm_obj.snapshot_manager().get(lambda ss: ss.name == name)
        return Snapshot(snapshot)

    def destroy_snapshot(self, snapshot_name: str):
        snapshot = self.vm_obj.snapshot_manager().get(lambda ss: ss.name == snapshot_name)
        if snapshot is not None:
            WaitForTask(snapshot.vim_obj.snapshot.Remove(removeChildren=False))
            return snapshot_name
        else:
            print("Invalid Snapshot Name: The Snapshot you designated does not exist")


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
    ) -> None:
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

