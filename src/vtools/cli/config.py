import configparser
import os
import typer
from typing_extensions import Annotated
from rich.console import Console

from vtools.esxi import ESXi
from vtools.exception import handle_exceptions

CONFIG_FILE = os.path.expanduser("~/.vtools_config")
app = typer.Typer()
console = Console()


@app.command(name='set', help='For setting a connection config.')
def set_config(
    ip: Annotated[str, typer.Option(help="Host IP", prompt=True)] = '',
    user: Annotated[str, typer.Option(help="User name", prompt=True)] = 'root',
    pwd: Annotated[str, typer.Option(help="Password", prompt=True)] = ''
):
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    config['CONNECTION'] = {'ip': ip, 'user': user, 'pwd': pwd}
    with open(CONFIG_FILE, "w") as config_file:
        config.write(config_file)


@app.command(name='get', help='For getting the current connection config.')
def get_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    if not config.has_section("CONNECTION"):
        console.print("Connection configuration not set.")
        console.print("Please use command 'vtools-cli config set --ip <HostIP> --user <username> --pwd <password>'")
        return

    connection_config = config['CONNECTION']
    for config_key in connection_config:
        console.print(f'{config_key} = {connection_config.get(config_key)}')


@handle_exceptions()
def connect():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    connection_config = config['CONNECTION']
    return ESXi(
        ip=connection_config.get('ip'),
        user=connection_config.get('user'),
        pwd=connection_config.get('pwd')
    )
