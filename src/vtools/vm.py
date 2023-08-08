import sys
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    TryAgain
)
from typing import (
    List
)

from pyVim.task import WaitForTask
from pyVmomi import vim

from vtools.cli.exception import handle_exceptions
from vtools.controller import Controller
from vtools.cpu import Cpu, CpuInfo
from vtools.disk import Disk
from vtools.snapshot import Snapshot
from vtools.query import QueryMixin
from vtools.vsphere import create_disk_spec, remove_disk_spec, create_controller_spec, remove_controller_spec,\
    list_snapshots_recursively


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
    def memory(self) -> int:
        return self.vim_obj.summary.config.memorySizeMB

    @property
    def num_cpus(self) -> int:
        return self.vim_obj.summary.config.numCpu

    def __repr__(self) -> str:
        return f'VM(vim_obj={self.vim_obj!r}, name={self.name}, ip={self.ips}, ' \
               f'memory={self.memory}, num_cpus={self.num_cpus})'

    def power_on(self) -> None:
        self._invoke_power_on()
        self._wait_until_power_state_is(vim.VirtualMachine.PowerState.poweredOn)

    def power_off(self) -> None:
        self._invoke_power_off()
        self._wait_until_power_state_is(vim.VirtualMachine.PowerState.poweredOff)

    def suspend(self):
        self._invoke_suspend()
        self._wait_until_power_state_is(vim.VirtualMachine.PowerState.suspended)

    def cpu_manager(self):
        return CpuManager(self)

    def memory_manager(self):
        return MemoryManager(self)

    def disk_manager(self):
        return DiskManager(self)

    def controller_manager(self):
        return ControllerManager(self)

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


class CpuManager(QueryMixin[Cpu]):
    def __init__(self, vm_obj: VM) -> None:
        self.vm_obj = vm_obj

    def info(self):
        return CpuInfo(self.vm_obj.vim_obj.runtime.host.hardware.cpuInfo)

    def _list_all(self) -> List[Cpu]:
        cpu_pkgs = self.vm_obj.vim_obj.runtime.host.hardware.cpuPkg
        return [Cpu(cpu_obj) for cpu_obj in cpu_pkgs]

    @handle_exceptions
    def edit(self, num_cpus: int):
        if self.vm_obj.power_state != "poweredOff":
            logger.error(f"The current state of the VM is {self.vm_obj.power_state}, please turn off the VM.")
            sys.exit()
        config_spec = vim.vm.ConfigSpec()
        config_spec.numCPUs = num_cpus
        task = self.vm_obj.vim_obj.ReconfigVM_Task(spec=config_spec)
        WaitForTask(task)


class MemoryManager:
    def __init__(self, vm_obj: VM) -> None:
        self.vm_obj = vm_obj

    def size(self) -> int:
        return self.vm_obj.vim_obj.config.hardware.memoryMB

    @handle_exceptions
    def edit(self, memory_size):
        if self.vm_obj.power_state != "poweredOff":
            logger.error(f"The current state of the VM is {self.vm_obj.power_state}, please turn off the VM.")
            sys.exit()
        config_spec = vim.vm.ConfigSpec()
        config_spec.memoryMB = memory_size
        task = self.vm_obj.vim_obj.ReconfigVM_Task(spec=config_spec)
        WaitForTask(task)


class SnapshotManager(QueryMixin[Snapshot]):
    def __init__(self, vm_obj: VM) -> None:
        self.vm_obj = vm_obj

    def _list_all(self) -> List[Snapshot]:
        snapshot_data = []
        snapshot = self.vm_obj.vim_obj.snapshot
        if snapshot is None:
            return snapshot_data
        else:
            list_snapshots_recursively(snapshot_data, snapshot.rootSnapshotList)
            return snapshot_data

    def create_snapshot(self, name: str,
                        description: str = None,
                        memory: bool = True,
                        quiesce: bool = False):
        if [vm_obj for vm_obj in self.vm_obj.snapshot_manager().list() if vm_obj.vim_obj.name == name]:
            logger.error(f"Invalid Name: The VM snapshot name {name} has already exist. ")
            sys.exit()
        task = self.vm_obj.vim_obj.CreateSnapshot(name, description, memory, quiesce)
        WaitForTask(task)
        snapshot = self.vm_obj.snapshot_manager().get(lambda ss: ss.name == name)
        return Snapshot(snapshot)

    def revert_snapshot(self, snapshot_name: str):
        snapshot = self.vm_obj.snapshot_manager().get(lambda ss: ss.name == snapshot_name)
        if snapshot is None:
            logger.error("Invalid Snapshot Name: The Snapshot you designated does not exist.")
            sys.exit()
        else:
            WaitForTask(snapshot.vim_obj.snapshot.Revert(suppressPowerOn=False))

    def destroy_snapshot(self, snapshot_name: str):
        snapshot = self.vm_obj.snapshot_manager().get(lambda ss: ss.name == snapshot_name)
        if snapshot is None:
            logger.error("Invalid Snapshot Name: The Snapshot you designated does not exist.")
            sys.exit()
        else:
            WaitForTask(snapshot.vim_obj.snapshot.Remove(removeChildren=False))


class DiskManager(QueryMixin[Disk]):
    def __init__(self, vm_obj: VM) -> None:
        self.vm_obj = vm_obj

    def _list_all(self) -> List[Disk]:
        return [Disk(disk_obj) for disk_obj in self.vm_obj.vim_obj.config.hardware.device
                if isinstance(disk_obj, vim.vm.device.VirtualDisk)]

    @handle_exceptions
    def add_disk(self, disk_size: int, disk_type: str):
        # Find appropriate unit number
        unit_number = 0
        controller = None
        for device in self.vm_obj.vim_obj.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualSCSIController):
                controller = device
                unit_number += 1
            if hasattr(device.backing, 'fileName'):
                unit_number = int(device.unitNumber) + 1
                if unit_number >= 16:
                    logger.error("we don't support this many disks on the SCSI Controller")
                    sys.exit()
        if controller is None:
            logger.error("Disk SCSI controller not found!")
            return None

        spec = create_disk_spec(controller, unit_number, disk_size, disk_type)
        task = self.vm_obj.vim_obj.ReconfigVM_Task(spec=spec)
        WaitForTask(task)
        return task.info

    @handle_exceptions
    def remove_disk(self, disk_num: int, disk_prefix_label='Hard disk '):
        disk_label = disk_prefix_label + str(disk_num)
        # Find the disk device
        virtual_disk_device = None
        for device in self.vm_obj.vim_obj.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualDisk) and device.deviceInfo.label == disk_label:
                virtual_disk_device = device
        if not virtual_disk_device:
            logger.error(f"Virtual {disk_label} could not be found.")
            sys.exit()

        spec = remove_disk_spec(virtual_disk_device)
        WaitForTask(self.vm_obj.vim_obj.ReconfigVM_Task(spec=spec))


class ControllerManager(QueryMixin[Controller]):
    def __init__(self, vm_obj: VM) -> None:
        self.vm_obj = vm_obj

    def _list_all(self) -> List[Controller]:
        for i in self.vm_obj.vim_obj.config.hardware.device:
            print(i.deviceInfo.label)
        return [Controller(controller_obj) for controller_obj in self.vm_obj.vim_obj.config.hardware.device
                if isinstance(controller_obj, vim.vm.device.VirtualController)]

    @handle_exceptions
    def add_scsi_controller(self):
        # Find appropriate bus number
        bus_number = 0
        for device in self.vm_obj.vim_obj.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualSCSIController):
                bus_number += 1

        spec = create_controller_spec(bus_number)
        task = self.vm_obj.vim_obj.ReconfigVM_Task(spec=spec)
        WaitForTask(task)

    @handle_exceptions
    def remove_scsi_controller(self, disk_num: int, disk_prefix_label='SCSI controller '):
        disk_label = disk_prefix_label + str(disk_num)
        # Find the disk device
        virtual_disk_device = None
        for device in self.vm_obj.vim_obj.config.hardware.device:
            if isinstance(device, vim.vm.device.ParaVirtualSCSIController)\
                    and device.deviceInfo.label == disk_label:
                virtual_disk_device = device
        if virtual_disk_device is None:
            logger.info(f"Virtual {disk_label} could not be found.")
            sys.exit()

        spec = remove_controller_spec(virtual_disk_device)
        WaitForTask(self.vm_obj.vim_obj.ReconfigVM_Task(spec=spec))
