from typing import (
    List
)

from pyVim.connect import SmartConnect
from pyVmomi import vim

from vtools.vsphere import get_first_vim_obj
from vtools.query import QueryMixin
from vtools.vm import VM
from vtools.datastore import Datastore


class ESXi:
    def __init__(
        self,
        ip: str = 'localhost',
        user: str = 'root',
        pwd: str = ''
    ) -> None:
        self.ip = ip
        self.user = user
        self.pwd = pwd

        self._login()

    def _login(self) -> None:
        self._si = SmartConnect(host=self.ip,
                                user=self.user,
                                pwd=self.pwd,
                                disableSslCertValidation=True)
        self._content = self._si.RetrieveContent()
        self.vim_obj = get_first_vim_obj(content=self._content,
                                         vim_type=vim.HostSystem)

    def datastore_manager(self):
        return DatastoreManager(self)

    def vm_manager(self):
        return VMManager(self)


class VMManager(QueryMixin[VM]):
    def __init__(self, esxi: ESXi) -> None:
        self.esxi = esxi

    def _list_all(self) -> List[VM]:
        return [VM(vm_vim_obj) for vm_vim_obj in self.esxi.vim_obj.vm]

    def create(self):
        pass


class DatastoreManager(QueryMixin[Datastore]):
    def __init__(self, esxi: ESXi) -> None:
        self.esxi = esxi

    def _list_all(self) -> List[Datastore]:
        return [
            Datastore(datastore_vim_obj)
            for datastore_vim_obj in self.esxi.vim_obj.datastore
        ]
