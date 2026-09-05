"""Build public/alpha-poker-starter.zip with reproducible bytes."""

from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "starter-kit"
DESTINATION = ROOT / "public" / "alpha-poker-starter.zip"
FILES = (
    (SOURCE / "bot.py", "bot.py"),
    (SOURCE / "bot.json", "bot.json"),
    (SOURCE / "README.md", "README.md"),
    (SOURCE / "API.md", "API.md"),
    (SOURCE / "WORKFLOWS.md", "WORKFLOWS.md"),
    (ROOT / "cli" / "pyproject.toml", "cli/pyproject.toml"),
    (ROOT / "cli" / "README.md", "cli/README.md"),
    (ROOT / "cli" / "alpha_poker_cli" / "__init__.py", "cli/alpha_poker_cli/__init__.py"),
    (ROOT / "cli" / "alpha_poker_cli" / "__main__.py", "cli/alpha_poker_cli/__main__.py"),
    (ROOT / "cli" / "alpha_poker_cli" / "main.py", "cli/alpha_poker_cli/main.py"),
)
FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def build() -> Path:
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(DESTINATION, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, archive_name in FILES:
            info = zipfile.ZipInfo(archive_name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return DESTINATION


if __name__ == "__main__":
    print(build())
