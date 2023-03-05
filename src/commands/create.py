"""Dedicated space for `create` project command."""

import os
import configparser
import click

from ..models.base_command import BaseCommand
from ..exceptions import handle_error, InputError, IntegrityError
from ..utils.docker_file import DockerFile
from ..utils.docker_compose import DockerCompose
from ..utils.git import GitUtils
from ..utils.helper import generate_password
from ..utils.helper import execute_command

from ..constants import DEF_ODOO_VERSION
from ..constants import DEF_ODOO_REPO
from ..constants import ODOO_SHALLOW
from ..constants import SUPPORTED_ODOO_VERSIONS
from ..constants import EXPECTED_KEY_PATHS


class CreateCommand(BaseCommand):  # pylint: disable=too-many-instance-attributes
    """
    Class that handles specific part of creating a new Odoo development project.
    """

    custom_structure: str
    odoo_version: str
    key_paths: dict
    git_repos: dict
    addons_repo: str | None
    no_build: bool
    docker_network_name: str
    pg_pass: str | None

    def __init__(self,
                 project_name: str,
                 odoo_version: str | None = None,
                 addons_repo: str | None = None,
                 no_build: bool = False) -> None:
        self.odoo_version = odoo_version or DEF_ODOO_VERSION
        self.addons_repo = addons_repo
        self.no_build = no_build
        self.pg_pass = None

        super().__init__(project_name)

    @handle_error
    def init_command(self) -> None:
        """
        Init command

        Raises:
            InputError: In case of invalid value for --odoo-version
        """
        super().init_command()

        if self.odoo_version not in SUPPORTED_ODOO_VERSIONS:
            allowed = '", "'.join(SUPPORTED_ODOO_VERSIONS)
            msg = f'Invalid value "{self.odoo_version}" for --odoo-version.{os.linesep}' \
                  f'Allowed values are "{allowed}"'
            raise InputError(msg)

    @handle_error
    def execute(self) -> None:
        """
        Main function called to execute the `create` command
        """
        project_structure = self.config.get_project_structure(
            custom_structure=self.custom_structure)

        project_path = os.path.join(
            self.config.workspace_dir, self.project_name)

        # Check if project already exists
        if os.path.isdir(project_path):
            raise IntegrityError(
                f'A directory "{self.project_name}" already exists in "{self.config.workspace_dir}"'
            )

        green_project_name = click.style(self.project_name, fg='green')
        click.echo(f'Creating project "{green_project_name}" using '
                   f'"{self.config.structure_file}" structure '
                   f'and Odoo version {self.odoo_version}')

        os.makedirs(project_path)

        self.key_paths = {
            'project': project_path
        }
        self.git_repos = {}

        self._create_structure(project_structure, project_path)

        self._setup_key_paths()

        self._build_docker_image()

    def _create_structure(self, struct: dict, path: str) -> None:
        """
        Recursive function that generates a folders structure based on input definition.

        Args:
            struct (dict): Structure definition
            path (str): Destination path
        """
        for key, val in struct.items():
            f_path = os.path.join(path, key)

            # Update the path in the key_paths dict
            f_key = val.get('key', False)
            if f_key:
                self.key_paths.update({f_key: f_path})

            # Update the path in the key_paths dict
            repo = val.get('repo', False)
            if repo:
                self.git_repos.update({f_key: repo})

            if val['type'] == 'file':
                with open(f_path, 'w', encoding='utf8'):
                    pass

                continue

            os.makedirs(f_path)

            if 'childs' in val:
                self._create_structure(val.get('childs'), f_path)

    def _setup_key_paths(self) -> None:
        """
        Every folder or file in the project structure can have a key
        corresponding to a function within this class.
        Calling the respective function will populate the folder or
        the file with relevant data.
        """
        for key in EXPECTED_KEY_PATHS:
            key_action = f'_struct_action_{key}'

            if key not in self.key_paths or not hasattr(self, key_action):
                continue

            path = self.key_paths[key]

            f_key_action = getattr(self, key_action)
            if not callable(f_key_action):
                continue

            f_key_action(path)

    def _struct_action_odoo(self, path: str) -> None:
        """
        Triggers the action clone odoo sources inside the odoo folder

        Args:
            path (str): The path to the odoo folder
        """
        odoo_repo = self.git_repos.get('odoo', DEF_ODOO_REPO)

        git = GitUtils(repo=odoo_repo,
                       branch=self.odoo_version,
                       shallow=ODOO_SHALLOW)
        git.clone(path)

    def _struct_action_custom_addons(self, path: str) -> None:
        """
        Triggers the action clone repo or only create an empty requirements.txt file

        Args:
            path (str): The path to the addons folder
        """
        addons_repo = self.addons_repo \
            or self.git_repos.get('custom_addons', None)

        if not addons_repo:
            # Create an empty requirements.txt file.
            with open(os.path.join(path, 'requirements.txt'), 'w', encoding='utf8'):
                pass

            return

        git = GitUtils(repo=addons_repo)
        git.clone(path)

    def _struct_action_docker_file(self, path: str) -> None:
        """
        Triggers the action to add content to the dockerfile

        Args:
            path (str): The path to the dockerfile
        """
        docker_file = DockerFile(self.odoo_version, self.key_paths)

        with open(path, 'w', encoding='utf8') as file_handle:
            file_handle.write(docker_file.get_content())

        docker_path = os.path.dirname(path)

        with open(os.path.join(docker_path, 'entrypoint.sh'), 'w', encoding='utf8') \
                as file_handle:
            file_handle.write(docker_file.get_entrypoint_content())

        with open(os.path.join(docker_path, 'wait-for-psql.py'), 'w', encoding='utf8') \
                as file_handle:
            file_handle.write(docker_file.get_wait_sql_content())

    def _struct_action_docker_compose(self, path: str) -> None:
        """
        Triggers the action to add content to the docker_compose.yml file.

        Args:
            path (str): The path to the docker_compose.yml file
        """
        docker_compose = DockerCompose(self.key_paths, self.project_name)

        with open(path, 'w', encoding='utf8') as file_handle:
            file_handle.write(docker_compose.get_content())

        self.docker_network_name = docker_compose.network_name

    def _struct_action_odoo_conf(self, path: str) -> None:
        """
        Triggers the action to populate the odoo.conf file.

        Args:
            path (str): The path to odoo.conf file
        """
        config = configparser.ConfigParser()
        admin_pass = generate_password()

        if not self.pg_pass:
            self.pg_pass = generate_password()

        config['options'] = {
            'admin_passwd': admin_pass,
            'addons_path': ','.join([
                '/mnt/odoo/odoo/addons',
                '/mnt/odoo/addons',
                '/mnt/addons'
            ]),
            'data_dir': '/var/lib/odoo',
            'db_host': 'db',
            'db_port': '5432',
            'db_user': 'odoo',
            'db_password': self.pg_pass,
            'db_name': self.project_name,
        }

        with open(path, 'w', encoding='utf8') as file_handle:
            config.write(file_handle)

    def _struct_action_env_file(self, path: str) -> None:
        """
        Triggers the action to populate the .env file.

        Args:
            path (str): The path to .env file
        """
        if not self.pg_pass:
            self.pg_pass = generate_password()

        env = {
            'POSTGRES_USER': 'odoo',
            'POSTGRES_PASSWORD': self.pg_pass
        }

        env_content = os.linesep.join([f'{k}="{v}"' for k, v in env.items()])

        with open(path, 'w', encoding='utf8') as file_handle:
            file_handle.write(env_content)

    def _build_docker_image(self) -> None:
        if self.no_build:
            click.echo('Skip building the docker image')
            click.echo('Execute this later by running `ocli build`')
            return

        cur_path = os.getcwd()

        proj_path = self.key_paths.get('project')
        if not proj_path:
            raise IntegrityError(
                'Error building docker images. Project path not found.')

        os.chdir(proj_path)
        click.echo("Building the docker image...")
        execute_command(['docker-compose', 'build', '--no-cache'])

        click.echo("Creating docker network...")
        execute_command(['docker', 'network', 'create', self.docker_network_name],
                        allow_error=True)
        os.chdir(cur_path)

    @staticmethod
    def init(cli) -> None:
        """
        Attaches the `create` command to the CLI.

        Argument:
            cli: The `cli` group function.
        """

        @cli.command(help='Create a new project')
        @click.argument('project_name', required=True)
        @click.option('-s', '--structure',
                      help='Custom project structure defined in configuration folder.')
        @click.option('-v', '--odoo-version',
                      help='Version of Odoo to be checked out.')
        @click.option('-r', '--addons-repo',
                      help='Git repository to be cloned into custom_addons folder.')
        @click.option('-n', '--no-build',
                      flag_value=True,
                      help='Don\'t build the docker image. '
                           'This implies that the action will be triggered manually later.')
        def create(project_name: str,
                   structure: str | None = None,
                   odoo_version: str | None = None,
                   addons_repo: str | None = None,
                   no_build: bool = False) -> None:
            """
            Entrypoint for the project `create` command.

            Args:
                project_name (str): Technical project name.
            """
            command = CreateCommand(project_name, odoo_version=odoo_version,
                                    addons_repo=addons_repo, no_build=no_build)
            command.custom_structure = structure
            command.execute()
