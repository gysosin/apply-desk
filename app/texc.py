"""Compile a CV or cover letter inside a bubblewrap sandbox.

Usage: python3 app/texc.py cv/main_x.tex | cover_letters/cover_x.tex

LuaTeX's \\directlua can read and write files, so agent-written TeX is never compiled
directly: here the home directory is hidden, the network is off, and only the
document's own folder is writable. cv/ -> lualatex (twice), cover_letters/ -> xelatex.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
TEX = HOME / ".TinyTeX"
ENGINES = {"cv": ("lualatex", 2), "cover_letters": ("xelatex", 1)}


def command(tex):
    folder = tex.parent
    engine, _ = ENGINES[folder.name]
    local_bin = HOME / ".local/bin"
    # Docker forbids mounting a fresh /proc inside the container; TeX doesn't need it, so mask it there instead.
    proc = ["--tmpfs", "/proc"] if os.environ.get("APPLYDESK_CONTAINER") else ["--proc", "/proc"]
    return ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", *proc, "--tmpfs", "/tmp",
            "--tmpfs", str(HOME),
            "--ro-bind", str(TEX), str(TEX), "--bind", str(TEX / "texmf-var"), str(TEX / "texmf-var"),
            *(["--ro-bind", str(local_bin), str(local_bin)] if local_bin.is_dir() else []),
            "--bind", str(folder), str(folder),
            "--unshare-all", "--die-with-parent", "--new-session", "--chdir", str(folder),
            "--setenv", "openout_any", "p", "--setenv", "openin_any", "p", "--setenv", "shell_escape", "f",
            engine, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", tex.name]


def main(arg):
    tex = (ROOT / arg).resolve()
    if tex.suffix != ".tex" or tex.parent.parent != ROOT or tex.parent.name not in ENGINES or not tex.is_file():
        sys.exit("usage: python3 app/texc.py cv/<file>.tex | cover_letters/<file>.tex")
    if not shutil.which("bwrap"):
        sys.exit("bubblewrap (bwrap) is required to compile safely")
    sys.path.insert(0, str(ROOT))
    from app.guards import TEX_DANGER
    # anything in the folder could be \input, so scan every text file there, not just the target
    for f in tex.parent.iterdir():
        if f.is_file() and f.suffix not in (".pdf", ".log", ".aux", ".out", ".otf", ".ttf") and f.stat().st_size < 2_000_000:
            if TEX_DANGER.search(f.read_text(encoding="utf-8", errors="replace")):
                sys.exit(f"refusing to compile: TeX file I/O or Lua primitives found in {f.name}")
    _, passes = ENGINES[tex.parent.name]
    for _ in range(passes):
        r = subprocess.run(command(tex), capture_output=True, text=True, timeout=300)
    print(r.stdout[-3000:])
    if r.returncode:
        print(r.stderr[-1500:], file=sys.stderr)
    for ext in (".aux", ".out"):
        tex.with_suffix(ext).unlink(missing_ok=True)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
