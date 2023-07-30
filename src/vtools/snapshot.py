from pyVmomi import vim


class Snapshot:
    def __init__(self, vim_obj: vim.vm.SnapshotTree) -> None:
        self.vim_obj = vim_obj

    @property
    def name(self) -> str:
        return self.vim_obj.name

    @property
    def description(self) -> str:
        return self.vim_obj.description

    def __repr__(self):
        return f'Snapshot(name={self.name}, description={self.description})'