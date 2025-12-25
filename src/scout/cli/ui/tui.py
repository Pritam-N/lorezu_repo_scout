from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import DataTable, Footer, Header, Input, Static, TabbedContent, TabPane

from scout.cli.ui.formatters import compute_offenders
from scout.core.models import Finding, ScanError, ScanResult


def _sev(v: object) -> str:
    return getattr(v, "value", str(v)).lower()


def _short(s: Optional[str], n: int = 160) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + "…"


def _count_by_severity(findings: List[Finding]) -> Dict[str, int]:
    out = {"critical": 0, "high": 0, "medium": 0, "low": 0, "other": 0}
    for f in findings:
        s = _sev(f.severity)
        if s in out:
            out[s] += 1
        else:
            out["other"] += 1
    return out


def _top_counts(items: List[str], top_n: int = 10) -> List[Tuple[str, int]]:
    counts: Dict[str, int] = {}
    for x in items:
        counts[x] = counts.get(x, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]


class SummaryView(Static):
    """
    A scrollable summary view rendered as Rich tables/panels.
    """

    def __init__(self) -> None:
        super().__init__()
        self._findings: List[Finding] = []
        self._errors: List[ScanError] = []
        self._result: Optional[ScanResult] = None

    def set_data(self, findings: List[Finding], errors: List[ScanError], result: Optional[ScanResult]) -> None:
        self._findings = findings
        self._errors = errors
        self._result = result
        self.refresh()

    def render(self):
        findings = self._findings
        errors = self._errors
        result = self._result

        # Derive unique targets from findings+errors (works for github multi-repo too)
        targets = set()
        for f in findings:
            if f.target:
                targets.add(f.target)
        for e in errors:
            if getattr(e, "target", None):
                targets.add(getattr(e, "target", None))

        sev_counts = _count_by_severity(findings)

        overview = Table(show_header=False, box=None, pad_edge=False)
        overview.add_column("k", style="bold")
        overview.add_column("v")
        overview.add_row("Targets", str(len(targets)) if targets else "-")
        overview.add_row("Findings", str(len(findings)))
        overview.add_row("Errors", str(len(errors)))

        # Include scan stats when available (scan-path provides this)
        if result is not None and getattr(result, "stats", None) is not None:
            s = result.stats
            scanner = "-"
            try:
                if result.targets and result.targets[0].meta:
                    scanner = str(result.targets[0].meta.get("scanner", "-"))
            except Exception:
                scanner = "-"
            stats = Table(show_header=False, box=None, pad_edge=False)
            stats.add_column("k", style="bold")
            stats.add_column("v")
            stats.add_row("Scanner", scanner)
            stats.add_row("Files considered", str(getattr(s, "files_considered", 0)))
            stats.add_row("Files scanned", str(getattr(s, "files_scanned", 0)))
            stats.add_row("Skipped binary", str(getattr(s, "files_skipped_binary", 0)))
            stats.add_row("Skipped too large", str(getattr(s, "files_skipped_too_large", 0)))
            stats.add_row("Duration (ms)", str(getattr(s, "duration_ms", 0)))
        else:
            stats = Table(show_header=False, box=None, pad_edge=False)
            stats.add_column("k", style="bold")
            stats.add_column("v")
            stats.add_row("Scanner", "-")
            stats.add_row("Files considered", "-")
            stats.add_row("Files scanned", "-")
            stats.add_row("Duration (ms)", "-")

        sev_table = Table(show_header=True, box=None, pad_edge=False)
        sev_table.add_column("Severity", style="bold")
        sev_table.add_column("Count", justify="right")
        for k in ["critical", "high", "medium", "low", "other"]:
            v = sev_counts.get(k, 0)
            if v:
                sev_table.add_row(k, str(v))
        if sev_table.row_count == 0:
            sev_table.add_row("—", "0")

        top_targets = _top_counts([f.target or "-" for f in findings], top_n=10)
        top_files = _top_counts([f"{f.target or '-'}:{f.file or '-'}" for f in findings], top_n=10)
        top_rules = _top_counts([f.rule_id or "-" for f in findings], top_n=10)

        top_t = Table(show_header=True, box=None, pad_edge=False)
        top_t.add_column("Top targets", style="bold")
        top_t.add_column("Findings", justify="right")
        if top_targets:
            for name, cnt in top_targets:
                top_t.add_row(_short(name, 60), str(cnt))
        else:
            top_t.add_row("—", "0")

        top_f = Table(show_header=True, box=None, pad_edge=False)
        top_f.add_column("Top files", style="bold")
        top_f.add_column("Findings", justify="right")
        if top_files:
            for name, cnt in top_files:
                top_f.add_row(_short(name, 80), str(cnt))
        else:
            top_f.add_row("—", "0")

        top_r = Table(show_header=True, box=None, pad_edge=False)
        top_r.add_column("Top rules", style="bold")
        top_r.add_column("Findings", justify="right")
        if top_rules:
            for name, cnt in top_rules:
                top_r.add_row(_short(name, 80), str(cnt))
        else:
            top_r.add_row("—", "0")

        return Group(
            Panel(overview, title="Overview", border_style="blue"),
            Panel(stats, title="Scan stats", border_style="blue"),
            Panel(sev_table, title="Severity breakdown", border_style="blue"),
            Panel(top_t, title="Top targets", border_style="blue"),
            Panel(top_f, title="Top files", border_style="blue"),
            Panel(top_r, title="Top rules", border_style="blue"),
        )


@dataclass(frozen=True)
class TUIData:
    findings: List[Finding]
    errors: List[ScanError]
    result: Optional[ScanResult] = None


class ResultsTUI(App):
    CSS = """
    Screen { overflow: hidden; }
    #toolbar { height: 3; padding: 0 1; }
    #filters { height: 3; padding: 0 1; }
    DataTable { height: 1fr; }
    Input { width: 1fr; }
    .pill { padding: 0 1; border: solid $panel; }
    #summary_scroll { height: 1fr; }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("/", "focus_search", "Search"),
        ("c", "clear_search", "Clear"),
    ]

    def __init__(self, data: TUIData, **kwargs):
        super().__init__(**kwargs)
        self.data = data
        self.query: str = ""

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="toolbar"):
            yield Static("secret-scout — Results", classes="pill")

        with Container(id="filters"):
            with Horizontal():
                yield Static("Search:", classes="pill")
                yield Input(placeholder="filter by repo/file/rule/message…", id="search")

        with TabbedContent():
            with TabPane("Findings", id="tab_findings"):
                yield DataTable(id="findings_table")

            with TabPane("Errors", id="tab_errors"):
                yield DataTable(id="errors_table")

            with TabPane("Top offenders", id="tab_offenders"):
                yield DataTable(id="offenders_repos")
                yield DataTable(id="offenders_files")
                yield DataTable(id="offenders_rules")

            with TabPane("Summary", id="tab_summary"):
                with VerticalScroll(id="summary_scroll"):
                    yield SummaryView()

        yield Footer()

    def on_mount(self) -> None:
        self._setup_findings_table()
        self._setup_errors_table()
        self._setup_offenders_tables()

        self._refresh_findings()
        self._refresh_errors()
        self._refresh_offenders()
        self._refresh_summary()

    # ----------------------------
    # Actions
    # ----------------------------

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_clear_search(self) -> None:
        inp = self.query_one("#search", Input)
        inp.value = ""
        self.query = ""
        self._refresh_findings()
        self._refresh_errors()
        self._refresh_offenders()
        # Summary should not be search-filtered; no refresh needed, but harmless:
        self._refresh_summary()

    # ----------------------------
    # Search
    # ----------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self.query = (event.value or "").strip().lower()
            self._refresh_findings()
            self._refresh_errors()
            self._refresh_offenders()

    def _match(self, *parts: str) -> bool:
        if not self.query:
            return True
        blob = " ".join([p for p in parts if p]).lower()
        return self.query in blob

    # ----------------------------
    # Setup tables
    # ----------------------------

    def _setup_findings_table(self) -> None:
        t = self.query_one("#findings_table", DataTable)
        t.cursor_type = "row"
        t.zebra_stripes = True
        t.add_columns("Repo", "Severity", "File", "Line", "Rule", "Message", "Sample/Hint")

    def _setup_errors_table(self) -> None:
        t = self.query_one("#errors_table", DataTable)
        t.cursor_type = "row"
        t.zebra_stripes = True
        t.add_columns("Target", "Message", "Detail")

    def _setup_offenders_tables(self) -> None:
        tr = self.query_one("#offenders_repos", DataTable)
        tf = self.query_one("#offenders_files", DataTable)
        tu = self.query_one("#offenders_rules", DataTable)

        for t in (tr, tf, tu):
            t.cursor_type = "row"
            t.zebra_stripes = True

        tr.add_columns("Repos/Targets", "Count")
        tf.add_columns("Files (target:file)", "Count")
        tu.add_columns("Rules", "Count")

    # ----------------------------
    # Refresh tables
    # ----------------------------

    def _refresh_findings(self) -> None:
        t = self.query_one("#findings_table", DataTable)
        t.clear()

        rows = sorted(
            self.data.findings,
            key=lambda f: (
                f.target or "",
                f.file or "",
                {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(_sev(f.severity), 9),
                f.rule_id or "",
                f.line or 0,
            ),
        )

        for f in rows:
            sev = _sev(f.severity)
            sample = f.sample or f.value_hint or ""
            kind = getattr(f.kind, "value", str(f.kind))
            if kind == "filename":
                sample = ""

            if not self._match(
                f.target or "",
                f.file or "",
                f.rule_id or "",
                f.message or "",
                sample,
                sev,
            ):
                continue

            t.add_row(
                f.target or "",
                sev,
                f.file or "",
                str(f.line or ""),
                f.rule_id or "",
                _short(f.message, 140),
                _short(sample, 140),
            )

    def _refresh_errors(self) -> None:
        t = self.query_one("#errors_table", DataTable)
        t.clear()

        for e in self.data.errors:
            detail = getattr(e, "detail", None) or ""
            if not self._match(e.target or "", e.message or "", detail):
                continue
            t.add_row(e.target or "", _short(e.message, 180), _short(detail, 180))

    def _refresh_offenders(self) -> None:
        offenders = compute_offenders(self.data.findings, top_n=15)

        tr = self.query_one("#offenders_repos", DataTable)
        tf = self.query_one("#offenders_files", DataTable)
        tu = self.query_one("#offenders_rules", DataTable)

        tr.clear()
        tf.clear()
        tu.clear()

        for name, count in offenders.by_target:
            if self._match(name):
                tr.add_row(name or "-", str(count))

        for name, count in offenders.by_file:
            if self._match(name):
                tf.add_row(name or "-", str(count))

        for name, count in offenders.by_rule:
            if self._match(name):
                tu.add_row(name or "-", str(count))

    def _refresh_summary(self) -> None:
        view = self.query_one(SummaryView)
        view.set_data(self.data.findings, self.data.errors, self.data.result)


def run_tui(*, findings: List[Finding], errors: List[ScanError], result: Optional[ScanResult] = None) -> None:
    ResultsTUI(TUIData(findings=findings, errors=errors, result=result)).run()