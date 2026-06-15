from __future__ import annotations

import typer

app = typer.Typer(help="DEHPS worker commands")


@app.command()
def version() -> None:
    from dehps import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()

