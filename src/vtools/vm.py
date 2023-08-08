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
from vtools.vsphere import create_disk_spec, list_snapshots_recursively


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

    def disk_manager(self):
        return DiskManager(self)

    def controller_manager(self):
        return ControllerManager(self)

    def snapshot_manager(self):
        return SnapshotManager(self)

    def cpu_manager(self):
        return CpuManager(self)

    # def memory_manager(self):
    #     return MemoryManager(self)

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


# class MemoryManager(QueryMixin[Memory]):
#     def __init__(self, vm_obj: VM) -> None:
#         self.vm_obj = vm_obj
#
#     def _list_all(self) -> List[Memory]:
#         snapshot_data = []
#         snapshot = self.vm_obj.vim_obj.snapshot
#         if snapshot is not None:
#             list_snapshots_recursively(snapshot_data, snapshot.rootSnapshotList)
#             return snapshot_data
#         else:
#             return snapshot_data

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
            logger.info(f"Invalid Name: The VM snapshot name {name} has already exist. ")
            sys.exit()
        task = self.vm_obj.vim_obj.CreateSnapshot(name, description, memory, quiesce)
        WaitForTask(task)
        snapshot = self.vm_obj.snapshot_manager().get(lambda ss: ss.name == name)
        return Snapshot(snapshot)

    def destroy_snapshot(self, snapshot_name: str):
        snapshot = self.vm_obj.snapshot_manager().get(lambda ss: ss.name == snapshot_name)
        if snapshot is None:
            logger.info("Invalid Snapshot Name: The Snapshot you designated does not exist.")
            sys.exit()
        else:
            WaitForTask(snapshot.vim_obj.snapshot.Remove(removeChildren=False))
            return snapshot_name


class DiskManager(QueryMixin[Disk]):
    def __init__(self, vm_obj: VM) -> None:
        self.vm_obj = vm_obj

    def _list_all(self) -> List[Disk]:
        return [Disk(disk_obj) for disk_obj in self.vm_obj.vim_obj.config.hardware.device
                if isinstance(disk_obj, vim.vm.device.VirtualDisk)]

    @handle_exceptions
    def add_disk(self, disk_size: int, disk_type: str):
        spec = vim.vm.ConfigSpec()
        unit_number = 0
        controller = None
        for device in self.vm_obj.vim_obj.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualSCSIController):
                controller = device
                unit_number += 1
            if hasattr(device.backing, 'fileName'):
                unit_number = int(device.unitNumber) + 1
                if unit_number >= 16:
                    logger.info("we don't support this many disks")
                    sys.exit()
        if controller is None:
            return None

        disk_spec = create_disk_spec(disk_size, disk_type)
        disk_spec.device.unitNumber = unit_number
        disk_spec.device.controllerKey = controller.key
        spec.deviceChange = [disk_spec]
        task = self.vm_obj.vim_obj.ReconfigVM_Task(spec=spec)
        WaitForTask(task)
        return Disk(task.info.result)

    @handle_exceptions
    def remove_disk(self, disk_num: int, disk_prefix_label='Hard disk '):
        disk_label = disk_prefix_label + str(disk_num)
        # Find the disk device
        virtual_disk_device = None
        for device in self.vm_obj.vim_obj.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualDisk) and device.deviceInfo.label == disk_label:
                virtual_disk_device = device
        if not virtual_disk_device:
            logger.info(f"Virtual {disk_label} could not be found.")
            sys.exit()

        spec = vim.vm.ConfigSpec()
        disk_spec = vim.vm.device.VirtualDeviceSpec()
        disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
        disk_spec.device = virtual_disk_device
        dev_changes = [disk_spec]
        spec.deviceChange = dev_changes
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
        bus_number = 0
        for device in self.vm_obj.vim_obj.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualSCSIController):
                bus_number += 1
        spec = vim.vm.ConfigSpec()
        scsi_ctr = vim.vm.device.VirtualDeviceSpec()
        scsi_ctr.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        scsi_ctr.device = vim.vm.device.ParaVirtualSCSIController()
        scsi_ctr.device.busNumber = bus_number
        scsi_ctr.device.hotAddRemove = True
        scsi_ctr.device.sharedBus = 'noSharing'
        scsi_ctr.device.scsiCtlrUnitNumber = 7
        spec.deviceChange = [scsi_ctr]
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
        spec = vim.vm.ConfigSpec()
        disk_spec = vim.vm.device.VirtualDeviceSpec()
        disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
        disk_spec.device = virtual_disk_device
        dev_changes = [disk_spec]
        spec.deviceChange = dev_changes
        WaitForTask(self.vm_obj.vim_obj.ReconfigVM_Task(spec=spec))
