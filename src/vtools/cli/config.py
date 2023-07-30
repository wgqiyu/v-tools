import configparser
import os
import typer
from typing_extensions import Annotated
from rich.console import Console
import sys

from vtools.esxi import ESXi

CONFIG_FILE = os.path.expanduser("~/.vtools_config")
app = typer.Typer()
console = Console()


@app.command(name='set', help='For setting a connection config.')
def set_config(
    ip: Annotated[str, typer.Option(help="Host IP", prompt=True)],
    user: Annotated[str, typer.Option(help="User name", prompt=True)],
    pwd: Annotated[str, typer.Option(help="Password", prompt=True)]
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
        console.print("Please use command 'python main.py config set --ip <HostIP> --user <username> --pwd <password>'")
        return

    connection_config = config['CONNECTION']
    for config_key in connection_config:
        console.print(f'{config_key} = {connection_config.get(config_key)}')


def connect():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    try:
        connection_config = config['CONNECTION']
    except Exception as e:
        print(f"ERROR: {e}. Please set a valid config using the command below:")
        print(f"\tpython main.py config set --ip <HostIP> --user <username> --pwd <password>")
        sys.exit()
    return ESXi(
        ip=connection_config.get('ip'),
        user=connection_config.get('user'),
        pwd=connection_config.get('pwd')
    )
