import typer

from vtools.cli import (
    config,
    vm,
    datastore
)

app = typer.Typer()
app.add_typer(config.app, name='config')
app.add_typer(vm.app, name="vm")
app.add_typer(datastore.app, name="datastore")


def main():
    app()


if __name__ == "__main__":
    main()
