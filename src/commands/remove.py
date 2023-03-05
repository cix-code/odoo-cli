"""Dedicated space for removing a project."""

import click
from ..models.base_command import BaseCommand


class RemoveCommand(BaseCommand):
    """
    Class that handles specific part of removing an odoo development project created by oCLI.
    """

    @staticmethod
    def init(cli) -> None:
        """
        Attaches the `remove` command to the CLI.

        Argument:
            cli: The `cli` group function.
        """

        @cli.command(help='Remove a project')
        @click.argument('project_name', required=True)
        def remove(project_name: str):
            """
            Entrypoint for the project `remove` command.

            Args:
                project_name (str): Technical project name.
            """

            red_project_name = click.style(project_name, fg='red')
            click.echo(f'Removing project {red_project_name}...')
