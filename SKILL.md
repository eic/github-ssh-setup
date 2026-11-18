---
name: github-ssh-setup
description: Set up and troubleshoot git-over-SSH to GitHub on Linux/macOS hosts (e.g. SDCC). Use when a git push/fetch/clone to github.com fails with "Permission denied (publickey)", when the user wants to switch repos from HTTPS to SSH remotes, generate or register an SSH key, set up a persistent ssh-agent, or when remote URLs contain embedded tokens.
---

# Git over SSH to GitHub

One script does the work: `scripts/github_ssh.py` next to this file (Python 3.6+, standard library only). Below, `GS` means `python3 <skill-dir>/scripts/github_ssh.py`. `README.md` holds the same steps for humans.

The `config` subcommand adds a `Host github.com` block to `~/.ssh/config` with `IdentityAgent ~/.ssh/agent.%L.sock`. ssh and git therefore find the agent without `SSH_AUTH_SOCK`, from any shell, including yours.

## Ground rules

- You cannot type a key passphrase. `GS add` and `ssh-keygen` prompt for one, so ask the user to run them in their own terminal. In Claude Code, suggest typing `! <command>` at the prompt only if it gives them a real TTY; otherwise a separate terminal.
- Never print tokens. `GS switch` masks `https://user:TOKEN@...` itself; keep the masking in anything you write. If tokens turn up, tell the user to revoke them at github.com/settings/tokens.
- `GS config` edits `~/.ssh/config`, and `GS switch` rewrites repo remotes. Run each with `-n` first, show the result, and wait for a go-ahead.

## Diagnose

Run `GS doctor`. It checks, in order: key files, the config block, an agent on the socket, a key loaded in it, and `ssh -T git@github.com`. Each failure prints its fix.

| First failing check | Fix |
|---|---|
| key | Setup step 1 |
| github.com block | `GS config -n`, then `GS config` |
| agent / key loaded | User runs `GS add` in their terminal |
| GitHub auth (all others ok) | Key not on GitHub: Setup step 2 |
| all ok, but push to an org repo refused | Key not authorized for the org's SSO: Setup step 2.3 |

If `~/.ssh/config` already has its own `Host github.com` entry, `GS config` prints the lines to merge rather than editing. Show them to the user.

## Setup (user-driven, one time)

1. **Key:** `ssh-keygen -t ed25519 -C "<email>" -f ~/.ssh/id_ed25519`, with a passphrase.
2. **GitHub:** the user adds `~/.ssh/id_ed25519.pub` under Settings → SSH and GPG keys → New SSH key (Authentication Key). You can show the `.pub` contents; it is public. If `gh` is authenticated, `gh ssh-key add ~/.ssh/id_ed25519.pub --title "<host>"` also works.
   3. For orgs that enforce SAML SSO: **Configure SSO** next to the key → authorize each org.
3. **Config and agent:** `GS config` (you, after the user confirms the dry run). Then the user runs `GS add`. The agent lasts until the host reboots or it is killed. After a reboot, or on another host sharing the home directory, they run `GS add` again.
4. **Verify:** `GS doctor`.

For a non-default key, pass `--key PATH` to `config`, `add` and `doctor`. On Windows, skip `config`/`add` and point the user at the README's Windows section.

## Switch remotes

Only repos cloned over HTTPS need this. `git@github.com:` remotes are already SSH.

```sh
GS switch -n <root> [--depth N] [--all]   # dry run; depth default 4
GS switch    <root> [--depth N] [--all]   # apply after the user confirms
```

By default it changes `origin` only; `--all` covers every remote (e.g. `upstream`). A repo whose `.git` is a file is a worktree. It shares config with its main repo, so it may already show as switched.

Afterwards, confirm with `git -C <repo> ls-remote origin HEAD` on two or three repos.

## Report

Give one line per item: repos switched, repos skipped (and why), credentials found (masked) and needing revocation, and anything left for the user to do (passphrase, GitHub key, SSO).
