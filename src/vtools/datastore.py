from pyVmomi import vim


class Datastore:
    def __init__(
        self,
        vim_obj: vim.Datastore
    ) -> None:
        self.vim_obj = vim_obj

    @property
    def name(self) -> str:
        return self.vim_obj.summary.name

    @property
    def type(self) -> str:
        return self.vim_obj.summary.type

    def __repr__(self):
        return f'Datastore(name="{self.name}", type="{self.type}")'
