import typer

from vtools.cli import (
    config,
    vm,
    datastore,
    disk,
    snapshot
)

app = typer.Typer()
app.add_typer(config.app, name='config', help="Operations related to connection configuration")
app.add_typer(vm.app, name="vm", help="Operations related to Virtual Machines (VM)")
app.add_typer(datastore.app, name="datastore", help="Operations related to Datastore")
app.add_typer(disk.app, name="disk", help="Operations related to Disk")
app.add_typer(snapshot.app, name="snapshot", help="Operations related to Snapshot")


def main():
    app()


if __name__ == "__main__":
    main()
