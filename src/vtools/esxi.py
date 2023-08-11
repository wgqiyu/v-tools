from functools import cached_property
from typing import List

from loguru import logger
from pyVim.connect import SmartConnect
from pyVim.task import WaitForTask
from pyVmomi import vim

from vtools.datastore import Datastore
from vtools.exception import InvalidStateError
from vtools.query import QueryMixin
from vtools.vm import (
    VM,
    OvfImportSpec
)
from vtools.vsphere import get_first_vim_obj


class ESXi:
    def __init__(
        self,
        vim_obj: vim.HostSystem = None,
        ip: str = 'localhost',
        user: str = 'root',
        pwd: str = ''
    ) -> None:
        if vim_obj is None:
            self.ip = ip
            self.user = user
            self.pwd = pwd

            self._login()
        else:
            self.vim_obj = vim_obj

            self.ip = None
            self.user = None
            self.pwd = None

    def __eq__(self, other):
        if isinstance(other, ESXi):
            return self.vim_obj == other.vim_obj
        return False

    def _login(self) -> None:
        self._si = SmartConnect(host=self.ip,
                                user=self.user,
                                pwd=self.pwd,
                                disableSslCertValidation=True)
        self._content = self._si.RetrieveContent()
        self.vim_obj = get_first_vim_obj(content=self._content,
                                         vim_type=vim.HostSystem)
        logger.info(f'Connected to ESXi(ip="{self.ip}") as "{self.user}"')

    @cached_property
    def datastores(self) -> "DatastoreManager":
        return DatastoreManager(self)

    @cached_property
    def vms(self) -> "VMManager":
        return VMManager(self)

    def get_vm_config_option(
        self,
        hardware_version: str = None
    ) -> vim.vm.ConfigOption:
        env_browser = self.vim_obj.parent.environmentBrowser
        return env_browser.QueryConfigOption(hardware_version, None)


class DatastoreManager(QueryMixin[Datastore]):
    def __init__(self, esxi: ESXi) -> None:
        self.esxi = esxi

    def _list_all(self) -> List[Datastore]:
        return [Datastore(datastore_vim_obj)
                for datastore_vim_obj in self.esxi.vim_obj.datastore]


class VMManager(QueryMixin[VM]):
    def __init__(self, esxi: ESXi) -> None:
        self.esxi = esxi

    def _list_all(self) -> List[VM]:
        return [VM(vm_vim_obj) for vm_vim_obj in self.esxi.vim_obj.vm]

    def create(self, name: str, spec: OvfImportSpec,
               datastore: Datastore) -> VM:
        return spec.create_vm(name, self.esxi, datastore)

    def delete(self, vm: VM) -> None:
        if vm.esxi != self.esxi:
            raise InvalidStateError()

        if vm.power_state != vim.VirtualMachine.PowerState.poweredOff:
            vm.power_off()
        WaitForTask(vm.vim_obj.Destroy())
