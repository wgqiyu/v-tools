import sys

from _socket import gaierror
from pyVmomi import vim
from requests.exceptions import MissingSchema, InvalidURL


def handle_exceptions():
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except KeyError as e:
                print(f"Exception occurred: {e}")
                print("Please set a config file using the command:")
                print("vtools-cli config set --ip <HostIP> --user <username> --pwd <password>")
            except ConnectionRefusedError as e:
                print(f"Exception occurred: {e}")
                print("Please check if the network connection and if the IP address is valid and try again.")
            except gaierror as e:
                print(f"Exception occurred: {e}")
                print("Please check if the network connection and if the IP address is valid and try again.")
            except vim.fault.InvalidLogin as e:
                print(f"Exception occurred: {e.msg}")
                print("Please set the correct username or password using the command:\n"
                      "vtools-cli config set --ip <HostIP> --user <username> --pwd <password>")
            except MissingSchema as e:
                print(f"Exception occurred: {e}. Please enter a valid url.")
            except InvalidURL as e:
                print(f"Exception occurred: {e}. Please enter a valid url.")
            # except vim.fault.HostConnectFault as e:
            #     print(f"Exception occurred: {e.msg}")
            #     print("Please secure internet connection and try again.")
            # except vim.fault.HostNotConnected as e:
            #     print(f"Exception occurred: {e}")
            except Exception as e:
                print(f"Exception occurred: {e}")
            sys.exit()
        return wrapper
    return decorator
