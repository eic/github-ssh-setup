#!/usr/bin/env python3
"""Set up and check git-over-SSH to GitHub. Standard library only, Python 3.6+.

Subcommands:
  config   add a `Host github.com` block to ~/.ssh/config pointing ssh at a
           fixed per-host agent socket (~/.ssh/agent.<host>.sock)
  add      start that agent if needed and load a key into it (asks for the
           passphrase; run it in an interactive terminal)
  doctor   check key, agent, config and GitHub authentication
  switch   change GitHub HTTPS remotes under a directory to SSH

Because ssh reads the socket path from ~/.ssh/config, no shell startup file
needs to set SSH_AUTH_SOCK. On Windows, use the built-in OpenSSH agent
service instead of `config`/`add` (see README).
"""
import argparse
import os
import re
import socket
import subprocess
import sys

HOME = os.path.expanduser("~")
SSH_DIR = os.path.join(HOME, ".ssh")
CONFIG = os.path.join(SSH_DIR, "config")
DEFAULT_KEY = os.path.join(SSH_DIR, "id_ed25519")
SOCK = os.path.join(SSH_DIR, "agent.%s.sock" % socket.gethostname().split(".")[0])
WINDOWS = os.name == "nt"
MARK = "# managed by github_ssh.py"
BLOCK = """{mark}
Host github.com
  User git
  IdentityAgent ~/.ssh/agent.%L.sock
  IdentityFile {key}
  AddKeysToAgent yes
"""
HTTPS_RE = re.compile(r"^https://(?:[^@/]+@)?github\.com/(.+?)(?:\.git)?/?$")


def run(cmd, env=None):
    return subprocess.run(cmd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, universal_newlines=True)


def agent_env():
    env = dict(os.environ)
    if not WINDOWS:
        env["SSH_AUTH_SOCK"] = SOCK
    return env


def mask(url):
    return re.sub(r"//[^@/]+@", "//***@", url)


def ensure_agent():
    """Start an agent on SOCK unless one already answers there."""
    if WINDOWS:
        return True
    if run(["ssh-add", "-l"], env=agent_env()).returncode != 2:
        return True
    if os.path.exists(SOCK):
        os.remove(SOCK)
    return run(["ssh-agent", "-a", SOCK]).returncode == 0


def cmd_config(a):
    if WINDOWS:
        sys.exit("On Windows use the OpenSSH agent service; see README.")
    key = a.key.replace(HOME, "~", 1)
    block = BLOCK.format(mark=MARK, key=key)
    text = open(CONFIG).read() if os.path.exists(CONFIG) else ""
    if MARK in text:
        print("%s already has the github.com block." % CONFIG)
        return
    if re.search(r"(?mi)^\s*Host\s+.*\bgithub\.com\b", text):
        print("%s already has a Host github.com entry; add these lines to it "
              "by hand:\n\n%s" % (CONFIG, block))
        return
    if a.dry_run:
        print("Would append to %s:\n\n%s" % (CONFIG, block))
        return
    os.makedirs(SSH_DIR, mode=0o700, exist_ok=True)
    # ssh uses the first matching value, so the block goes first.
    with open(CONFIG, "w") as f:
        f.write(block + ("\n" + text if text else ""))
    os.chmod(CONFIG, 0o600)
    print("Added github.com block to %s" % CONFIG)


def cmd_add(a):
    if not os.path.exists(a.key):
        sys.exit("No key at %s. Create one: ssh-keygen -t ed25519 -f %s"
                 % (a.key, a.key))
    if not ensure_agent():
        sys.exit("Could not start ssh-agent on %s" % SOCK)
    if a.hours:
        cmd = ["ssh-add", "-t", "%dh" % a.hours, a.key]
    else:
        cmd = ["ssh-add", a.key]
    # Inherit the terminal so ssh-add can prompt for the passphrase.
    sys.exit(subprocess.call(cmd, env=agent_env()))


def cmd_doctor(a):
    ok = True

    def report(good, msg, fix=""):
        nonlocal ok
        ok = ok and good
        print("%s %s%s" % ("ok  " if good else "FAIL", msg,
                           "\n     -> " + fix if fix and not good else ""))

    report(os.path.exists(a.key) and os.path.exists(a.key + ".pub"),
           "key %s" % a.key, "ssh-keygen -t ed25519 -f %s" % a.key)
    if not WINDOWS:
        text = open(CONFIG).read() if os.path.exists(CONFIG) else ""
        report(MARK in text, "github.com block in %s" % CONFIG,
               "github_ssh.py config")
        rc = run(["ssh-add", "-l"], env=agent_env()).returncode
        report(rc != 2, "agent on %s" % SOCK, "github_ssh.py add")
        report(rc == 0, "key loaded in agent", "github_ssh.py add")
    r = run(["ssh", "-T", "-o", "BatchMode=yes", "git@github.com"],
            env=agent_env())
    m = re.search(r"Hi (\S+?)!", r.stdout)
    out = r.stdout.strip().splitlines()
    fix = ("fix the items above first" if not ok else
           "add %s.pub at https://github.com/settings/keys" % a.key)
    report(bool(m), "GitHub auth" + (" as %s" % m.group(1) if m else
                                     ": " + out[-1] if out else ""), fix)
    sys.exit(0 if ok else 1)


def find_repos(root, depth):
    root = os.path.abspath(root)
    base = root.rstrip(os.sep).count(os.sep)
    for d, dirs, files in os.walk(root):
        level = d.rstrip(os.sep).count(os.sep) - base
        if ".git" in dirs or ".git" in files:
            yield d
        dirs[:] = [x for x in dirs if x != ".git" and level < depth - 1]


def cmd_switch(a):
    leaked = False
    for repo in find_repos(a.root, a.depth):
        r = run(["git", "-C", repo, "remote"])
        names = r.stdout.split() if r.returncode == 0 else []
        if not a.all:
            names = [n for n in names if n == "origin"]
        for name in names:
            url = run(["git", "-C", repo, "remote", "get-url", name]).stdout.strip()
            m = HTTPS_RE.match(url)
            if not m:
                continue
            new = "git@github.com:%s.git" % m.group(1)
            flag = ""
            if mask(url) != url:
                flag, leaked = "  [credential in URL: revoke it]", True
            if a.dry_run:
                print("would switch %s %s: %s -> %s%s" % (repo, name, mask(url), new, flag))
            elif run(["git", "-C", repo, "remote", "set-url", name, new]).returncode == 0:
                print("%s %s -> %s%s" % (repo, name, new, flag))
            else:
                print("FAILED %s %s" % (repo, name))
    if leaked:
        print("\nRevoke the flagged tokens at https://github.com/settings/tokens")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    sub.required = True
    for name, fn, hlp in [("config", cmd_config, "add github.com block to ~/.ssh/config"),
                          ("add", cmd_add, "start agent and load key"),
                          ("doctor", cmd_doctor, "check the whole setup"),
                          ("switch", cmd_switch, "switch HTTPS remotes to SSH")]:
        s = sub.add_parser(name, help=hlp)
        s.set_defaults(fn=fn)
        if name != "switch":
            s.add_argument("--key", default=DEFAULT_KEY, help="private key (default: %(default)s)")
        if name in ("config", "switch"):
            s.add_argument("-n", "--dry-run", action="store_true", help="show changes, make none")
        if name == "add":
            s.add_argument("--hours", type=int, help="unload the key after this many hours")
        if name == "switch":
            s.add_argument("root", nargs="?", default=".", help="directory to search (default: .)")
            s.add_argument("--depth", type=int, default=4,
                           help="directory levels below root to search (default: 4)")
            s.add_argument("--all", action="store_true",
                           help="switch every remote, not just origin")
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
