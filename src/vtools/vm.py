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
        return f'VM(vim_obj={self.vim_obj!r}, name={self.name}, memory={self.memory}, num_cpus={self.num_cpus})'

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
    def __init__(self, vm_obj: VM) -> None:
        self.vm_obj = vm_obj

    def _list_all(self) -> List[Disk]:
        return [Disk(disk_vm_obj) for disk_vm_obj
                in self.vm_obj.vim_obj.config.hardware.device
                if isinstance(disk_vm_obj, vim.vm.device.VirtualDisk) or
                isinstance(disk_vm_obj, vim.vm.device.ParaVirtualSCSIController)]

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
                    print("we don't support this many disks")
                    return
        if controller is None:
            print("Disk SCSI controller not found! Please use the below command:")
            print("\tpython main.py disk add_controller <vm_name>")
            sys.exit()

        disk_spec = create_disk_spec(disk_size, disk_type)
        disk_spec.device.unitNumber = unit_number
        disk_spec.device.controllerKey = controller.key
        spec.deviceChange = [disk_spec]
        task = self.vm_obj.vim_obj.ReconfigVM_Task(spec=spec)
        WaitForTask(task)
        return Disk(task.info.result)

    def remove_disk(self, disk_num: int, disk_prefix_label='Hard disk '):
        disk_label = disk_prefix_label + str(disk_num)
        # Find the disk device
        virtual_disk_device = None
        for device in self.vm_obj.vim_obj.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualDisk) and device.deviceInfo.label == disk_label:
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
        WaitForTask(self.vm_obj.vim_obj.ReconfigVM_Task(spec=spec))
