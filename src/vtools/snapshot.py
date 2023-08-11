from enum import Enum
from typing import List

from pyVmomi import vim


def flatten_snapshot_tree(
    from_list: List[vim.vm.SnapshotTree],
    to_list: List[vim.vm.SnapshotTree]
) -> None:
    if not from_list:
        return

    for snapshot_tree in from_list:
        to_list.append(snapshot_tree)
        flatten_snapshot_tree(snapshot_tree.childSnapshotList, to_list)


def find_snapshot_tree(
    from_list: List[vim.vm.SnapshotTree],
    by_snapshot: vim.vm.Snapshot,
) -> vim.vm.SnapshotTree:
    for snapshot_tree in from_list:
        if snapshot_tree.snapshot == by_snapshot:
            return snapshot_tree

        if snapshot_tree.childSnapshotList:
            matched_child_snapshot_tree = find_snapshot_tree(
                snapshot_tree.childSnapshotList,
                by_snapshot
            )
            if matched_child_snapshot_tree is not None:
                return matched_child_snapshot_tree
    return None


class SnapshotType(Enum):
    SIMPLE = (False, False)
    QUIESCED = (False, True)
    MEMORY = (True, False)

    def __init__(self, is_memory: bool, is_quiesced: bool) -> None:
        self.is_memory = is_memory
        self.is_quiesced = is_quiesced


class Snapshot:
    def __init__(
        self,
        vim_obj: vim.vm.Snapshot,
        snapshot_tree_vim_obj: vim.vm.SnapshotTree
    ) -> None:
        self.vim_obj = vim_obj
        self._snapshot_tree_vim_obj = snapshot_tree_vim_obj

    def __repr__(self):
        return f'Snapshot(vim_obj={self.vim_obj!r})'

    @property
    def name(self) -> str:
        return self._snapshot_tree_vim_obj.name

    @property
    def description(self) -> str:
        return self._snapshot_tree_vim_obj.description
