import typer
import sys
from loguru import logger

from vtools.cli import (
    config,
    vm,
    datastore,
)

logger.remove(0)
logger.add(sys.stderr, level="ERROR")

app = typer.Typer()
app.add_typer(config.app, name='config', help="Operations related to connection configuration")
app.add_typer(vm.app, name="vm", help="Operations related to Virtual Machines (VM)")
app.add_typer(datastore.app, name="datastore", help="Operations related to datastore")


def main():
    app()


if __name__ == "__main__":
    main()
