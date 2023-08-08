import sys

from _socket import gaierror
from pyVmomi import vim
from requests.exceptions import MissingSchema, InvalidURL
from rich.console import Console

console = Console()


def handle_exceptions(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyError as e:
            console.print(f"Exception occurred: {e}")
            console.print("Please set a config file using the command:")
            console.print("vtools-cli config set --ip <HostIP> --user <username> --pwd <password>")
        except ConnectionRefusedError as e:
            console.print(f"Exception occurred: {e}")
            console.print("Please check if the network connection and if the IP address is valid and try again.")
        except gaierror as e:
            console.print(f"Exception occurred: {e}")
            console.print("Please check if the network connection and if the IP address is valid and try again.")
        except vim.fault.InvalidLogin as e:
            console.print(f"Exception occurred: {e.msg}")
            console.print("Please set the correct username or password using the command:\n"
                          "vtools-cli config set --ip <HostIP> --user <username> --pwd <password>")
        except vim.fault.InvalidDeviceSpec as e:
            console.print(f"Exception occurred: {e.msg}")
            for i in range(len(e.faultMessage)):
                console.print(e.faultMessage[i].message)
        except AttributeError as e:
            console.print(f"Exception occurred: {e}")
        except MissingSchema as e:
            console.print(f"Exception occurred: {e}. Please enter a valid url.")
        except InvalidURL as e:
            console.print(f"Exception occurred: {e}. Please enter a valid url.")
        except Exception as e:
            console.print(f"Exception occurred: {e}")
        sys.exit()
    return wrapper
