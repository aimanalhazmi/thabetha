import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"


def test_no_module_imports_system_pool_directly() -> None:
    offenders: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        rel = path.relative_to(APP_ROOT).as_posix()
        if rel in {"repositories/system_tasks.py", "repositories/__init__.py"}:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.repositories":
                if any(alias.name == "system_pool" for alias in node.names):
                    offenders.append(rel)
    assert offenders == []


def test_handle_new_user_is_security_definer() -> None:
    migrations = "\n".join(path.read_text() for path in (Path(__file__).resolve().parents[3] / "supabase/migrations").glob("0*.sql"))
    assert "function public.handle_new_user()" in migrations
    assert "security definer" in migrations.lower()


def test_elevated_connection_module_documents_allow_list() -> None:
    text = (APP_ROOT / "repositories/system_tasks.py").read_text()
    assert "lazy commitment-score sweeper" in text
    assert "elevated_connection" in text
