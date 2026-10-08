"""Phone push via ntfy.sh (no account; the topic name is the address)."""
import urllib.request


def send(cfg, message, title="Apply Desk", when=True, force=False):
    if not when or not (cfg.get("notify_enabled") or force) or not cfg.get("ntfy_topic"):
        return False
    req = urllib.request.Request(f"https://ntfy.sh/{cfg['ntfy_topic']}", data=message.encode("utf-8"),
                                 headers={"Title": title.encode("utf-8"), "Tags": "briefcase"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return 200 <= r.status < 300
