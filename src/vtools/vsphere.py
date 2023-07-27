from typing import (
    List,
    Optional,
    Type
)

from pyVmomi import vim
from pyVmomi.VmomiSupport import ManagedObject


def list_vim_obj(
    content: vim.ServiceInstanceContent,
    vim_type: Type[vim.ManagedEntity],
    container_vim_obj: vim.ManagedEntity = None,
    recurse: bool = True
) -> List[ManagedObject]:
    if not container_vim_obj:
        container_vim_obj = content.rootFolder

    types_in_view = [vim_type]
    container_view = content.viewManager.CreateContainerView(container_vim_obj,
                                                             types_in_view,
                                                             recurse)
    vim_obj_list = list(container_view.view)
    container_view.Destroy()
    return vim_obj_list


def get_first_vim_obj(
    content: vim.ServiceInstanceContent,
    vim_type: Type[vim.ManagedEntity],
    container_vim_obj: vim.ManagedEntity = None,
    recurse: bool = True
) -> Optional[ManagedObject]:
    vim_obj_list = list_vim_obj(content, vim_type, container_vim_obj, recurse)
    if len(vim_obj_list) > 0:
        return vim_obj_list[0]
    return None


def get_vim_obj_by_name(
    content: vim.ServiceInstanceContent,
    vim_type: Type[vim.ManagedEntity],
    name: str,
    container_vim_obj: vim.ManagedEntity = None,
    recurse: bool = True
) -> Optional[ManagedObject]:
    vim_obj_list = list_vim_obj(content, vim_type, container_vim_obj, recurse)
    for vim_obj in vim_obj_list:
        if vim_obj.name == name:
            return vim_obj
    return None
