"""Common part of all `commands` that oCLI can execute"""

from .config import Config
from ..exceptions import handle_error
from ..utils.helper import validate_project_name


class BaseCommand:
    """Abstract class inherited by all commands of oCLI"""

    config: Config
    project_name: str

    def __init__(self, project_name) -> None:
        self.project_name = project_name
        self.init_command()

    @handle_error
    def init_command(self):
        """
        Init command
        """
        validate_project_name(self.project_name)
        self.load_config()


    @handle_error
    def execute(self) -> None:
        """Main function called to execute a command"""

    def load_config(self) -> None:
        """Loads configuration"""

        self.config = Config()

    @staticmethod
    def init(cli) -> None:
        """
        Abstract definition for the `init` function.
        It is responsible for attaching the command to the oCLI.

        Argument:
            cli: The `cli` group function.

        Raises:
            NotImplementedError: This should never be reached
        """
        raise NotImplementedError()
