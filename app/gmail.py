"""Gmail check for employer replies: IMAP EXAMINE (never marks, moves or sends), then an AI pass
classifies each new email (ack / assessment / interview / offer / rejection) and moves the tracker row forward."""
import email
import html
import imaplib
import json
import re
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from app import agent, notify, store

REPLIES = store.DATA / "replies.json"
SEEN = store.DATA / "gmail_seen.json"
BACKFILLED = store.DATA / "gmail_backfilled"  # set once the first 180-day pass completes
# Last Gmail UID a finished run covered: later runs only ask for newer mail (UIDs grow with arrival).
STATE = store.DATA / "gmail_state.json"
# Rows an email can still move. Skipped / needs-review count too: you may have applied anyway.
OPEN = ("drafted", "skipped", "needs_review", "applied", "interview", "offer")
STATUS_FOR = {"ack": "applied", "assessment": "interview", "interview": "interview", "offer": "offer", "rejection": "rejected"}
BANNED = store.DATA / "banned_names.txt"
# Gmail-side prefilter (X-GM-RAW). All Mail, not INBOX: Gmail archives most ATS replies.
QUERY = ('newer_than:{days}d -in:sent -in:chats -category:promotions -category:social '
         '(application OR applying OR applied OR interview OR offer OR candidacy OR candidate OR assessment OR "next steps")')
FIRST_RUN_DAYS, DAYS, BATCH = 180, 30, 120
SKIP_SUBJECT = re.compile(r"security code|verification code|verify your|job alert|jobs you may|new jobs|is hiring|are hiring", re.I)
# LinkedIn sends application updates from jobs-noreply@; its other senders are alerts, digests and posts.
SKIP_SENDER = re.compile(r"(jobalerts|newsletters|groups|notifications|messages|updates|messaging-digest)-noreply@linkedin\.com", re.I)


def _h(v):
    return str(make_header(decode_header(v or ""))).strip()


def _text(msg):
    """Readable body: the plain-text part, else the HTML part with tags stripped (many ATS send HTML only)."""
    plain = markup = ""
    for part in msg.walk():
        kind = part.get_content_type()
        if kind not in ("text/plain", "text/html") or part.get_filename():
            continue
        try:
            body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
        except Exception:
            continue
        if kind == "text/plain":
            plain = plain or body
        else:
            markup = markup or html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(style|script|head)\b.*?</\1>", " ", body)))
    # Links carry no meaning for the AI and some plain parts are only a footer of tracking links: keep the part with more words.
    plain, markup = (re.sub(r"\s+", " ", re.sub(r"https?://\S+", " ", t)).strip() for t in (plain, markup))
    return plain if len(plain) >= len(markup) * 0.5 else markup


def banned(text, names):
    """Side-work names never enter the job pipeline (their mail is not a job reply)."""
    low = text.lower()
    return any(n.lower() in low for n in names)


def _clean(text):
    """Tracker notes are CSV: keep third-party text to one comma-free line."""
    return re.sub(r'[,"\s]+', " ", text).strip()


def _words(role):
    return set(re.findall(r"[a-z0-9]+", (role or "").lower())) - {"senior", "sr", "i", "ii", "iii", "the", "and", "of"}


def same_role(a, b):
    """Loose title match: one title's words contain the other's ("Backend" ~ "Backend Engineer II")."""
    wa, wb = _words(a), _words(b)
    return bool(wa and wb) and (wa <= wb or wb <= wa)


def _only_row(company, role, path):
    """The one tracker row for this company and role, matched loosely (the AI may word the title differently)."""
    rows = [a for a in store.applications(path)
            if company and a["company"].lower() == company.strip().lower() and same_role(a["role"], role)]
    return rows[0] if len(rows) == 1 else None


def apply_signals(results, mails, apps, path=None):
    """Write each classified email to its tracker row (forward moves only). Returns a line per change."""
    by_id = {a["id"]: a for a in apps}
    changes = []
    # Oldest first, so an ack then a rejection for the same new company ends at rejected.
    for r in sorted(results, key=lambda r: (mails.get(r.get("id")) or {}).get("date") or ""):
        m, status = mails.get(r.get("id")), STATUS_FOR.get(r.get("signal"))
        a = by_id.get(r.get("application_id")) or _only_row(r.get("company"), r.get("role"), path)
        company, role = (a["company"], a["role"]) if a else (_clean(r.get("company") or ""), _clean(r.get("role") or ""))
        if not (m and status and company and role):
            continue
        reason = f" - {_clean(re.sub(r'[()]', '', r['reason']))}" if r.get("reason") else ""  # brackets would end the reason early
        when, note = (m["date"] or "")[:10], f"gmail: {r['signal']}{reason} ({_clean(m['subject'])})"
        if not a and store.add_row({"date": when, "company": company, "role": role, "channel": "online", "status": status,
                                    "notes": f"Added by Gmail check{f' | applied {when}' if status == 'applied' else ''} | {when} {note}"}, path):
            changes.append(f"{company} ({role}): new -> {status}")
        elif store.advance(company, role, status, note, when, path):
            changes.append(f"{company} ({role}): -> {status}")
    return changes


def classify(fresh, apps, ctx):
    """One lean AI call per batch. Emails go in with short numeric ids (Message-IDs are long); only job mail comes back."""
    cfg = store.load_config()
    listing = "\n".join(f"{a['id']} | {a['company']} | {a['role']} | {a['status']}" for a in apps)
    emails = json.dumps([{"id": str(n), **{k: m[k] for k in ("date", "from", "subject", "body")}} for n, m in enumerate(fresh)])
    out = agent.run(agent.prompt("replies.md", apps=listing, emails=emails), model=cfg["models"]["score"], lean=True,
                    schema=agent.REPLIES, scratch=ctx.scratch, log=ctx.log, cancelled=ctx.cancelled, max_turns=3, tools=[])
    ids = {str(n): m["id"] for n, m in enumerate(fresh)}
    return [{**r, "id": ids[r["id"]]} for r in out["results"] if r.get("id") in ids]


def load_replies():
    return json.loads(REPLIES.read_text()) if REPLIES.exists() else []


def _record(fresh, results, apps):
    """Apply one classified batch: tracker updates plus the replies list the dashboard shows."""
    results = {r["id"]: r for r in results}
    changes = apply_signals(list(results.values()), {f["id"]: f for f in fresh}, apps)
    companies = {a["id"]: a["company"] for a in apps}
    found = []
    for f in fresh:
        r = results.get(f["id"], {})
        if r.get("signal", "other") != "other":
            found.append({"id": f["id"], "date": f["date"], "from": f["from"], "subject": f["subject"], "snippet": f["body"][:240],
                          "signal": r["signal"], "company": companies.get(r.get("application_id")) or r.get("company"),
                          "application_id": r.get("application_id") if r.get("application_id") in companies else None})
    merged = sorted({r["id"]: r for r in load_replies() + found}.values(), key=lambda r: r["date"], reverse=True)[:200]
    REPLIES.write_text(json.dumps(merged, indent=2))
    return found, changes


def search_args(state, validity, backfilled):
    """IMAP UID SEARCH criteria: only mail after the last checked UID when that UID is still valid."""
    days = DAYS if backfilled else FIRST_RUN_DAYS
    raw = ["X-GM-RAW", '"%s"' % QUERY.format(days=days).replace('"', '\\"')]
    if backfilled and state.get("uidvalidity") == validity and state.get("last_uid"):
        return ["UID", f"{state['last_uid'] + 1}:*", *raw]
    return raw


def gmail_check(ctx):
    cfg = store.load_config()
    if not cfg["gmail_enabled"] or not cfg["gmail_app_password"]:
        return "Gmail check is off (add an app password in Settings)"
    seen = json.loads(SEEN.read_text()) if SEEN.exists() else []
    seen_set, names = set(seen), [n.strip() for n in BANNED.read_text().splitlines() if n.strip()] if BANNED.exists() else []
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    store.DATA.mkdir(parents=True, exist_ok=True)
    found, changes, read = [], [], 0
    ctx.log(f"Connecting to Gmail as {cfg['gmail_user']}…")
    with imaplib.IMAP4_SSL("imap.gmail.com", timeout=30) as m:
        m.login(cfg["gmail_user"], cfg["gmail_app_password"])
        m.select('"[Gmail]/All Mail"', readonly=True)
        validity = m.response("UIDVALIDITY")[1][0].decode()
        args = search_args(state, validity, BACKFILLED.exists())
        _, ids = m.uid("SEARCH", *args)
        # "UID n:*" always returns the newest message even when it is older than n; drop it.
        last = state.get("last_uid", 0) if args[0] == "UID" else 0
        uids = [u for u in ids[0].split() if int(u) > last][-1000:]
        newest = max([int(u) for u in uids], default=last)
        ctx.log(f"Gmail: {len(uids)} new matching email(s) since the last check" if args[0] == "UID"
                else f"Gmail search, full pass{' of the last %d days' % FIRST_RUN_DAYS if not BACKFILLED.exists() else ''}: {len(uids)} matching emails")
        # Headers only, in one request; full bodies only for the emails the AI will read.
        heads = []
        if uids:
            _, data = m.uid("FETCH", b",".join(uids), "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])")
            for part in data:
                if isinstance(part, tuple):
                    uid = re.search(rb"UID (\d+)", part[0]).group(1)
                    h = email.message_from_bytes(part[1])
                    heads.append((uid, h.get("Message-ID") or uid.decode(), _h(h.get("From")), _h(h.get("Subject")), h.get("Date")))
        todo, noise = [], []
        for head in heads:
            uid, key, sender, subject, _ = head
            if key in seen_set:
                continue
            noisy = SKIP_SUBJECT.search(subject) or SKIP_SENDER.search(sender) or banned(f"{sender} {subject}", names)
            (noise if noisy else todo).append(key if noisy else head)
        seen += noise
        SEEN.write_text(json.dumps(seen[-5000:]))
        ctx.log(f"{len(todo)} new to read, {len(noise)} skipped as alerts or noise, {len(heads) - len(todo) - len(noise)} already checked")
        # Oldest batch first, so an ack lands before the rejection that follows it.
        for start in range(0, len(todo), BATCH):
            if ctx.cancelled():
                raise RuntimeError("cancelled")
            batch, fresh = todo[start:start + BATCH], []
            ctx.log(f"Batch {start // BATCH + 1}/{-(-len(todo) // BATCH)}: downloading {len(batch)} emails…")
            _, data = m.uid("FETCH", b",".join(h[0] for h in batch), "(UID BODY.PEEK[])")
            bodies = {re.search(rb"UID (\d+)", p[0]).group(1): p[1] for p in data if isinstance(p, tuple)}
            for uid, key, sender, subject, when in batch:
                body = _text(email.message_from_bytes(bodies.get(uid, b"")))
                if banned(body, names):
                    continue
                try:
                    when = parsedate_to_datetime(when).isoformat()
                except (TypeError, ValueError):
                    when = ""
                fresh.append({"id": key, "date": when, "from": parseaddr(sender)[1] or sender, "subject": subject, "body": body[:2000]})
            if fresh:
                ctx.log(f"AI is reading {len(fresh)} emails…")
                apps = [a for a in store.applications() if a["status"] in OPEN]  # fresh each batch: rows may have been added
                f, c = _record(fresh, classify(fresh, apps, ctx), apps)
                found += f
                changes += c
                for r in f:
                    ctx.log(f"  {r['signal']}: {r['company'] or r['from']} - {r['subject']}")
                for line in c:
                    ctx.log(f"  Tracker: {line}")
            read += len(fresh)
            seen += [h[1] for h in batch]
            SEEN.write_text(json.dumps(seen[-5000:]))  # progress survives a crash or cancel
    BACKFILLED.touch()
    STATE.write_text(json.dumps({"uidvalidity": validity, "last_uid": max(newest, state.get("last_uid", 0) if state.get("uidvalidity") == validity else 0)}))
    if changes or found:
        offers = [r["company"] or r["from"] for r in found if r["signal"] == "offer"]
        head = f"OFFER from {', '.join(offers)}! " if offers else ""
        notify.send(cfg, head + ("; ".join(changes) or f"{len(found)} new email(s) about your applications"), title="Apply Desk: replies")
    ctx.log(f"Done. {len(changes)} tracker update(s)." if changes else "Done. No tracker changes.")
    return f"Read {read} emails: {len(found)} about applications, {len(changes)} tracker updates"
