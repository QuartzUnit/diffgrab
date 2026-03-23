"""CLI interface for diffgrab — web page change tracking."""

from __future__ import annotations

import asyncio
import sys


def main() -> None:
    """Entry point for the diffgrab CLI."""
    try:
        from click import argument, group, option
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        print("CLI dependencies not installed. Run: pip install 'diffgrab[cli]'", file=sys.stderr)
        sys.exit(1)

    console = Console()

    @group()
    def cli() -> None:
        """diffgrab — Web page change tracking with structured diffs."""

    @cli.command()
    @argument("url")
    @option("--interval", default=24, type=int, help="Check interval in hours (default: 24).")
    @option("--db", default="", help="Custom database path.")
    def track(url: str, interval: int, db: str) -> None:
        """Register a URL for change tracking."""
        from diffgrab import track as _track

        kwargs = {"db_path": db} if db else {}
        result = asyncio.run(_track(url, interval, **kwargs))
        console.print(result)

    @cli.command()
    @argument("url", required=False, default=None)
    @option("--db", default="", help="Custom database path.")
    def check(url: str | None, db: str) -> None:
        """Check tracked URLs for changes."""
        from diffgrab import check as _check

        kwargs = {"db_path": db} if db else {}
        results = asyncio.run(_check(url, **kwargs))

        if not results:
            console.print("[dim]No tracked URLs found.[/dim]")
            return

        for r in results:
            if r.changed:
                console.print(f"[bold red]CHANGED[/bold red] {r.url}")
                console.print(f"  +{r.added_lines} / -{r.removed_lines} lines")
                if r.changed_sections:
                    console.print(f"  Sections: {', '.join(r.changed_sections[:5])}")
                console.print(f"  {r.summary}")
            else:
                console.print(f"[green]OK[/green] {r.url} — {r.summary}")

    @cli.command()
    @argument("url")
    @option("--before", "before_id", default=None, type=int, help="Snapshot ID for before.")
    @option("--after", "after_id", default=None, type=int, help="Snapshot ID for after.")
    @option("--db", default="", help="Custom database path.")
    def diff(url: str, before_id: int | None, after_id: int | None, db: str) -> None:
        """Show structured diff between two snapshots."""
        from diffgrab import diff as _diff

        kwargs = {"db_path": db} if db else {}
        result = asyncio.run(_diff(url, before_id, after_id, **kwargs))

        if not result.changed:
            console.print(f"[green]{result.summary}[/green]")
            return

        console.print(f"[bold]Diff for {result.url}[/bold]")
        console.print(f"+{result.added_lines} / -{result.removed_lines} lines")
        if result.changed_sections:
            console.print(f"Sections: {', '.join(result.changed_sections)}")
        console.print()
        console.print(result.unified_diff)

    @cli.command()
    @argument("url")
    @option("--count", default=10, type=int, help="Number of snapshots to show (default: 10).")
    @option("--db", default="", help="Custom database path.")
    def history(url: str, count: int, db: str) -> None:
        """Show snapshot history for a URL."""
        from diffgrab import history as _history

        kwargs = {"db_path": db} if db else {}
        snapshots = asyncio.run(_history(url, count, **kwargs))

        if not snapshots:
            console.print(f"[dim]No snapshots for {url}[/dim]")
            return

        table = Table(title=f"Snapshots for {url}")
        table.add_column("ID", style="cyan")
        table.add_column("Title")
        table.add_column("Words", justify="right")
        table.add_column("Hash", max_width=12)
        table.add_column("Captured At")

        for s in snapshots:
            table.add_row(
                str(s["id"]),
                s.get("title", ""),
                str(s.get("word_count", 0)),
                s["content_hash"][:12],
                s["captured_at"],
            )

        console.print(table)

    @cli.command()
    @argument("url")
    @option("--db", default="", help="Custom database path.")
    def untrack(url: str, db: str) -> None:
        """Remove a URL from tracking."""
        from diffgrab import untrack as _untrack

        kwargs = {"db_path": db} if db else {}
        result = asyncio.run(_untrack(url, **kwargs))
        console.print(result)

    cli()


if __name__ == "__main__":
    main()
