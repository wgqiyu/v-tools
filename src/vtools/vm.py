from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    TryAgain
)

from pyVim.task import WaitForTask
from pyVmomi import vim


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

    def __repr__(self) -> str:
        return f'VM(vim_obj={self.vim_obj!r})'

    def power_on(self) -> None:
        self._invoke_power_on()
        self._wait_until_power_state_is(vim.VirtualMachine.PowerState.poweredOn)

    def power_off(self) -> None:
        self._invoke_power_off()
        self._wait_until_power_state_is(
            vim.VirtualMachine.PowerState.poweredOff)

    def suspend(self):
        WaitForTask(self.vim_obj.Suspend())

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
