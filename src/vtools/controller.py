from pyVmomi import vim


class Controller:
    def __init__(
        self,
        vim_obj: vim.vm.device.VirtualDevice
    ) -> None:
        self.vim_obj = vim_obj

    @property
    def name(self) -> str:
        return self.vim_obj.deviceInfo.label

    @property
    def description(self) -> str:
        return self.vim_obj.deviceInfo.summary

    def __repr__(self):
        return f'Controller(name={self.name}, Description={self.description})'
