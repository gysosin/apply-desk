"""Tool policy for every agent the app runs (wired in as a PreToolUse hook).

This is the code-level guarantee that agents only research, write documents and
compile them: no browser, no form tools, no git, no uploads, no writes outside the
document folders. check() returns None when a call is allowed, else the reason.
"""
import re
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRITE_DIRS = ("cv", "cover_letters", "documents/applications", "company_research")
NO_READ = ("app/data", ".git", ".venv")
CHAIN = {"&&", "||", ";", "|", "&"}
READ_ONLY_CMDS = {"ls", "cat", "head", "tail", "grep", "wc", "echo", "pdfinfo", "true"}
REDIRECTS = {">", ">>", "<"}
TEX_SUFFIXES = (".tex", ".cls", ".sty", ".def", ".cfg", ".ltx", ".lua")
# Write-capable commands accept only these flags (blocks -t/--target-directory, --output-directory, ...).
FLAG_ALLOW = {
    "cp": {"-f", "-p", "-n"}, "mkdir": {"-p"}, "rm": {"-f"},
}
CLEAN_SUFFIXES = (".aux", ".log", ".out", ".txt", ".toc", ".xdv", ".fls", ".fdb_latexmk", ".synctex.gz", ".json")
# curl: allowlist only. Flags that take a value consume the next token.
CURL_FLAGS = {"-s", "-S", "-L", "-I", "-i", "-f", "-k", "--silent", "--show-error", "--location", "--head", "--include",
              "--fail", "--compressed", "--insecure"}
CURL_VALUE_FLAGS = {"-A", "-H", "-m", "--user-agent", "--header", "--max-time", "--retry", "--connect-timeout"}


def _resolve(p, cwd):
    p = Path(p).expanduser()
    return (p if p.is_absolute() else cwd / p).resolve()


def _under(p, base):
    return p == base or p.is_relative_to(base)


def readable(p, scratch):
    if scratch and _under(p, scratch.resolve()):
        return True
    return _under(p, ROOT) and not any(_under(p, ROOT / d) for d in NO_READ) and p.name != ".env"


def writable(p, scratch):
    if scratch and _under(p, scratch.resolve()):
        return True
    return any(_under(p, ROOT / d) for d in WRITE_DIRS)


def _check_bash(cmd, scratch):
    if any(c in cmd for c in ("$", "`", "\n")):
        return "shell substitution and multi-line commands are not allowed"
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.commenters = ""  # bash treats a mid-word # literally; validating everything after a # is stricter, not looser
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError as e:
        return f"unparseable command: {e}"
    for t in toks:
        if re.fullmatch(r"[<>&|;]+", t) and t not in CHAIN | REDIRECTS:
            return f"unsupported shell operator {t}"
    cwd, seg = ROOT, []
    for tok in toks + [";"]:
        if tok not in CHAIN:
            seg.append(tok)
            continue
        if seg:
            res = _check_segment(seg, cwd, scratch)  # cwd never changes: cd is rejected
            if isinstance(res, str):
                return res
        seg = []
    return None


def _check_segment(seg, cwd, scratch):
    """Returns the new cwd if allowed, else a reason string."""
    args, i = [], 0
    while i < len(seg):  # strip redirections, checking their targets
        t = seg[i]
        if t in (">", ">>") or (t.isdigit() and i + 1 < len(seg) and seg[i + 1] in (">", ">>")):
            if t.isdigit():
                i += 1
            target = seg[i + 1] if i + 1 < len(seg) else ""
            if target != "/dev/null" and not target.startswith("&") and not writable(_resolve(target, cwd), scratch):
                return f"redirect to {target} is outside the document folders"
            if target.endswith(TEX_SUFFIXES):
                return "TeX files may only be written with the Write/Edit tools"
            i += 2
            continue
        if t == "<":
            if i + 1 >= len(seg) or not readable(_resolve(seg[i + 1], cwd), scratch):
                return "input redirect from a disallowed path"
            i += 2
            continue
        args.append(t)
        i += 1
    if not args:
        return cwd
    prog, rest = args[0], args[1:]
    if prog != "curl" and any(re.search(r"[*?\[\]{}~]", a) for a in args):
        return "globs, brace and tilde expansion are not allowed"
    plain = [a for a in rest if not a.startswith("-")]
    allowed_flags = FLAG_ALLOW.get(prog)
    if allowed_flags is not None:
        bad = [a for a in rest if a.startswith("-") and a not in allowed_flags and not a.startswith("-interaction=")]
        if bad:
            return f"{prog} flag {bad[0]} is not allowed"

    if prog in ("cd", "pushd", "popd"):
        return "cd is not allowed; use paths relative to the repo root"
    if prog in ("lualatex", "xelatex", "luatex", "pdflatex", "latexmk", "xetex", "tex"):
        return "compile with: python3 app/texc.py cv/<file>.tex (sandboxed)"
    if prog in ("python", "python3"):
        if not rest or rest[0].startswith("-"):  # no interpreter flags at all (-c, -m, -cCODE, ...)
            return "python may only run tools/*.py and app/texc.py"
        script = _resolve(rest[0], cwd)
        ok = (script.parent == ROOT / "tools" and script.suffix == ".py") or script == ROOT / "app" / "texc.py"
        return cwd if ok else "python may only run tools/*.py and app/texc.py"
    if prog == "bun":
        ok = (len(rest) >= 2 and rest[0] == "run" and not rest[1].startswith("-")
              and _resolve(rest[1], cwd).is_relative_to(ROOT / ".agents/skills") and rest[1].endswith("/cli/src/cli.ts"))
        return cwd if ok else "bun may only run the portal CLIs"
    if prog == "curl":
        i = 0
        while i < len(rest):
            a = rest[i]
            if a in CURL_VALUE_FLAGS:
                v = rest[i + 1] if i + 1 < len(rest) else ""
                numeric = a in ("-m", "--max-time", "--retry", "--connect-timeout")
                if v.startswith("@") or (numeric and not v.replace(".", "", 1).isdigit()):
                    return f"curl value for {a} is not allowed"
                i += 2
                continue
            if a.startswith("-") and not (a in CURL_FLAGS or (not a.startswith("--") and set(a[1:]) <= set("sSLIifk"))):
                return f"curl may only GET pages (flag {a} is not allowed)"
            if not a.startswith("-") and not a.startswith(("http://", "https://")):
                return "curl may only fetch http(s) URLs"
            i += 1
        return cwd
    if prog == "pdftotext":
        ops, i = [], 0
        while i < len(rest):
            a = rest[i]
            if a in ("-f", "-l"):
                if i + 1 >= len(rest) or not rest[i + 1].isdigit():
                    return f"pdftotext {a} needs a page number"
                i += 2
                continue
            if a == "-enc":
                if i + 1 >= len(rest) or rest[i + 1] not in ("UTF-8", "Latin1", "ASCII7"):
                    return "pdftotext -enc must be UTF-8, Latin1 or ASCII7"
                i += 2
                continue
            if a.startswith("-") and a != "-":
                if a not in ("-layout", "-raw", "-nopgbrk", "-q", "-bbox"):
                    return f"pdftotext flag {a} is not allowed"
            else:
                ops.append(a)
            i += 1
        if not 1 <= len(ops) <= 2 or not readable(_resolve(ops[0], cwd), scratch):
            return "pdftotext usage: pdftotext [flags] <readable pdf> [out|-]"
        if len(ops) == 2 and ops[1].endswith(TEX_SUFFIXES):
            return "TeX files may only be written with the Write/Edit tools"
        if len(ops) == 2 and ops[1] != "-" and not writable(_resolve(ops[1], cwd), scratch):
            return "pdftotext output must go to the document folders or stdout"
        return cwd
    if prog == "rm":
        if any(set(a) & set("rR") for a in rest if a.startswith("-")):
            return "recursive rm is not allowed"
        for a in plain:
            p = _resolve(a, cwd)
            if not (writable(p, scratch) and p.name.endswith(CLEAN_SUFFIXES)):
                return f"rm only cleans LaTeX/build leftovers in the document folders, not {a}"
        return cwd
    if prog == "mkdir":
        return cwd if plain and all(writable(_resolve(a, cwd), scratch) for a in plain) else "mkdir outside the document folders"
    if prog == "cp":
        if len(plain) < 2:
            return "cp needs a source and destination"
        srcs, dst = plain[:-1], plain[-1]
        if not writable(_resolve(dst, cwd), scratch):
            return f"cp destination {dst} is outside the document folders"
        if dst.endswith(TEX_SUFFIXES) and any(
                not any(_resolve(x, cwd).is_relative_to(ROOT / d) for d in ("cv", "cover_letters")) for x in srcs):
            return "TeX files may only be copied from cv/ or cover_letters/"
        return cwd if all(readable(_resolve(s, cwd), scratch) for s in srcs) else "cp source is not readable"
    if prog == "grep":
        # grep [-nicvlwoHhEF | -A/B/C<n>] PATTERN [FILE...]; no -e/-f/-r: the first operand is always the pattern
        for a in rest:
            if a.startswith("--") or (a.startswith("-") and not re.fullmatch(r"-(?:[nicvlwoHhEF]+|[ABC]\d+)", a)):
                return f"grep flag {a} is not allowed"
    if prog in READ_ONLY_CMDS:
        for a in rest:
            if a.startswith("-") and ("=" in a or "/" in a or a in ("-f", "--file")):
                return f"{prog} flag {a} is not allowed"
        operands = [] if prog == "echo" else plain[1:] if prog == "grep" else plain  # grep's first operand is the pattern
        for a in operands:
            if not readable(_resolve(a, cwd), scratch):  # fail closed, existing or not
                return f"{prog} may not read {a}"
        return cwd
    return f"command '{prog}' is not allowed"


# TeX primitives that read/write arbitrary files or run code (LuaTeX \\directlua etc.).
TEX_DANGER = re.compile(r"\^\^|catcode|csname|ExplSyntax|lua_|directlua|luaexec|luacode|latelua|write18|\\openout|\\openin|\\immediate|"
                        r"\\(?:input|include|InputIfFileExists)\b(?!\s*\{[\w-]+(?:\.tex)?\})", re.I)


def _tex_content_ok(tool, inp):
    path = str(inp.get("file_path", ""))
    if not path.endswith(TEX_SUFFIXES):
        return None
    if path.endswith(".lua"):
        return "writing Lua files is not allowed"
    texts = [inp.get("content", ""), inp.get("new_string", "")] + [e.get("new_string", "") for e in inp.get("edits") or []]
    return "TeX file I/O and Lua primitives are not allowed in documents" if any(TEX_DANGER.search(t or "") for t in texts) else None


def check(tool, inp, scratch=None):
    if tool == "Bash":
        return _check_bash(inp.get("command", ""), scratch)
    if tool in ("Write", "Edit", "MultiEdit"):
        p = _resolve(inp.get("file_path", ""), ROOT)
        if not writable(p, scratch):
            return f"writes are limited to {', '.join(WRITE_DIRS)}"
        return _tex_content_ok(tool, inp)
    if tool in ("Read", "Glob", "Grep"):
        p = _resolve(inp.get("file_path") or inp.get("path") or ROOT, ROOT)
        return None if readable(p, scratch) else f"reading {p} is not allowed"
    if tool in ("WebFetch", "WebSearch", "TodoWrite", "Skill", "StructuredOutput"):
        return None
    return f"tool {tool} is not available to job-search agents"


def hook(scratch):
    """PreToolUse hook for claude-agent-sdk; runs even for pre-approved tools."""
    async def _hook(input_data, tool_use_id, context):
        reason = check(input_data.get("tool_name", ""), input_data.get("tool_input") or {}, scratch)
        if reason is None:
            return {}
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": reason}}
    return _hook
