from typing import (
    Any,
    List,
    Callable,
    TypeVar,
    Generic
)

T = TypeVar("T")


def by(
    field: str,
    condition: Callable[[Any], bool]
) -> Callable[[T], bool]:
    def _by_condition(obj):
        return condition(getattr(obj, field))
    return _by_condition


def by_name(condition: Callable[[Any], bool]) -> Callable[[T], bool]:
    return by("name", condition)


class QueryMixin(Generic[T]):
    def list(
        self,
        condition: Callable[[T], bool] = None
    ) -> List[T]:
        all_items = self._list_all()

        if condition is None:
            return all_items
        return [item for item in all_items
                if condition(item)]

    def get(self, condition: Callable[[T], bool]) -> T:
        for item in self._list_all():
            if condition(item):
                return item
        return None
