from pyVmomi import vim


class Disk:
    def __init__(
        self,
        vim_obj: vim.vm.device.VirtualDevice
    ) -> None:
        self.vim_obj = vim_obj

    @property
    def name(self) -> str:
        return self.vim_obj.deviceInfo.label

    @property
    def size(self) -> str:
        return self.vim_obj.deviceInfo.summary

    def __repr__(self):
        return f'Disk(name={self.name}, size={self.size})'
