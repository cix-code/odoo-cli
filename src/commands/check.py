"""Dedicated space for checking integrity of a project."""

import click
from ..models.base_command import BaseCommand


class CheckCommand(BaseCommand):
    """
    Class that handles specific part of checking an odoo development project created by oCLI.
    """

    @staticmethod
    def init(cli) -> None:
        """
        Attaches the `check` command to the CLI.

        Argument:
            cli: The `cli` group function.
        """

        @cli.command(help='Check integrity of a project')
        @click.argument('project_name', required=True)
        def check(project_name: str):
            """
            Entrypoint for the project `check` command.

            Args:
                project_name (str): Technical project name.
            """

            green_project_name = click.style(project_name, fg='green')
            click.echo(f'Checking integrity of project {green_project_name}...')
