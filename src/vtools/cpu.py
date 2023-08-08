from pyVmomi import vim


class CpuInfo:
    def __init__(
        self,
        cpu_info: vim.host.CpuInfo
    ) -> None:
        self.cpu_info = cpu_info

    @property
    def num_cores(self) -> int:
        return self.cpu_info.numCpuCores

    @property
    def num_pkgs(self) -> int:
        return self.cpu_info.numCpuPackages

    @property
    def num_threads(self) -> int:
        return self.cpu_info.numCpuThreads


class Cpu:
    def __init__(
        self,
        cpu_obj: vim.host.CpuPackage
    ) -> None:
        self.cpu_obj = cpu_obj

    @property
    def idx(self) -> int:
        return self.cpu_obj.index

    @property
    def description(self) -> str:
        return self.cpu_obj.description

    def __repr__(self):
        return f'CPU(index="{self.idx}", description="{self.description}")'
