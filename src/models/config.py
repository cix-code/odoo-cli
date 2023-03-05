"""
Config definition of oCLI
"""

import os
import configparser
import click
import yaml

from ..constants import APP_NAME
from ..constants import DEF_STRUCTURE_YML
from ..constants import DEF_PROJECT_STRUCTURE
from ..constants import EXPECTED_KEY_PATHS

from ..exceptions import UserAbortError, ConfigError
from ..utils.helper import validate_yml_file


class Config:
    """
    Config class provide useful functions to read and store configuration values
    oCLI stores an ocli.conf file in user's default configuration folder
    """

    conf_file_path: str
    conf_path: str
    structure_file: str

    # Config values
    workspace_dir: str

    def __init__(self) -> None:

        app_path = click.get_app_dir(APP_NAME)
        if not os.path.isdir(app_path):
            os.makedirs(app_path)

        self._set_conf_path()

        self.load_config()

    def _set_conf_path(self) -> None:
        """
        Prepares the conf file path.
        If the app folder doesn't exist, it gets created.
        """

        app_path = click.get_app_dir(APP_NAME)
        if not os.path.isdir(app_path):
            os.makedirs(app_path)

        self.conf_path = app_path
        self.conf_file_path = os.path.join(app_path, 'ocli.conf')

    def load_config(self) -> None:
        """
        Loads the config values from the config file.
        Creates the config file if it doesn't exist.
        """

        # Create new config file with default values if no config exists yet
        if not os.path.exists(self.conf_file_path):
            click.echo('Configuration file not found. Attempting to create it.')
            self.load_default_values()
            self.store_config_file()

        config = configparser.ConfigParser()

        try:
            config.read(self.conf_file_path)
        except configparser.Error as err:
            raise ConfigError(err.message) from err

        self.workspace_dir = config.get('Workspace', 'workspace_dir')
        if not self.workspace_dir:
            raise ConfigError(
                '"workspace_dir" not found in configuration file')

        if not os.path.isdir(self.workspace_dir):
            raise ConfigError(
                f'Path {self.workspace_dir} configured '
                'as "workspace_dir" does not exist')

    def load_default_values(self) -> None:
        "Sets default config values"

        self.workspace_dir = os.getcwd()

        click.echo(
            f'The following will be your workspace directory: {self.workspace_dir}')

        # Get user's confirmation to use current path as workspace folder
        cont = click.confirm('Continue?', default=True)
        if not cont:
            important = click.style('Important!', fg='red')
            raise UserAbortError(f'{important} Execute the `ocli` command in the '
                                 'folder that will be your workspace.')

    def store_config_file(self) -> None:
        """
        Stores the configuration in a config file
        """

        config = configparser.ConfigParser()

        config['Workspace'] = {
            'workspace_dir': self.workspace_dir,
        }

        # Create a new section
        config['Projects'] = {}

        # Save the config file
        with open(self.conf_file_path, 'w', encoding='utf8') as conf_file:
            conf_file.writelines([
                f'# This is the configuration file for oCLI{os.linesep}',
                f'# Do not change this file manually{os.linesep}',
                os.linesep
            ])
            config.write(conf_file)

    def get_project_structure(self, custom_structure=None) -> dict:
        """
        Reads the project structure configured in the structure yml file.

        Returns:
            dict: the project structure
        """
        struct_file_name = DEF_STRUCTURE_YML

        if custom_structure and validate_yml_file(custom_structure):
            struct_file_name = custom_structure

        self.structure_file = struct_file_name

        struct_file_path = os.path.join(self.conf_path, struct_file_name)

        if not os.path.exists(struct_file_path):
            if custom_structure:
                raise ConfigError(
                    f'The file {custom_structure} supposed to define the project structure '
                    'doesn\'t exist'
                )
            self.create_default_project_structure()

        with open(struct_file_path, 'r', encoding='utf8') as yml_file:
            data = yaml.load(yml_file, Loader=yaml.SafeLoader)

        self.validate_project_structure(data)

        return data

    def create_default_project_structure(self):
        """
        Generates the default.yml file that represents default structure supported by oCLI
        """
        f_path = os.path.join(self.conf_path, DEF_STRUCTURE_YML)

        click.echo(f'Default structure definition not found.{os.linesep}'
                   f'Generating default structure in {f_path}')

        # Save the yml file
        with open(f_path, 'w', encoding='utf8') as yml_file:
            yml_file.writelines([
                f'# This is the default project structure for oCLI{os.linesep}',
                f'# !!! Do not change this file{os.linesep}',
                '# If you need a custom structure copy this file and then run the '
                f'`ocli create [PROJECT_NAME] -s [CUSTOM_NAME].yml`{os.linesep}',
                os.linesep
            ])

            yaml.dump(DEF_PROJECT_STRUCTURE, yml_file)

    def validate_project_structure(self, struct: dict, is_root: bool = True, key_items=None):
        """
        Validates the project structure as follows:
        - Makes sure that every item in the structure is a dir or file
        - Makes sure that all necessary files are specified
        """

        key_items = key_items if isinstance(key_items, list) else []
        invalid_conf_msg = f'Invalid project structure in {self.structure_file}.{os.linesep}'
        if not isinstance(struct, dict):
            raise ConfigError(f'{invalid_conf_msg}- Invalid file format.')

        for key, val in struct.items():
            if not isinstance(val, dict):
                raise ConfigError(
                    f'{invalid_conf_msg}- Invalid value at key "{key}"')

            f_type = val.get('type', False)
            if not f_type:
                raise ConfigError(
                    f'{invalid_conf_msg}- Invalid type for "{key}"')

            f_key = val.get('key', False)
            if f_key:
                key_items.append(f_key)

            if 'childs' in val:
                self.validate_project_structure(
                    val['childs'], is_root=False, key_items=key_items)

        if not is_root:
            return

        # Make sure all following keys are in the configured structure
        expected_keys = set(EXPECTED_KEY_PATHS)

        if len(set(key_items).intersection(expected_keys)) != len(expected_keys):
            raise ConfigError(
                f'{invalid_conf_msg}- Expected key items are not found')
