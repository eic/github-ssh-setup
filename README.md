# SSH access to GitHub

Set up git-over-SSH to GitHub with one Python script (standard library only, Python 3.6+). It works the same from any shell (bash, zsh, tcsh) on Linux and macOS. The folder is also a Claude Code skill: once installed, Claude can diagnose SSH failures and switch your repos for you.

| File | Purpose |
|---|---|
| `SKILL.md` | Instructions Claude follows when the skill is used |
| `scripts/github_ssh.py` | `config`, `add`, `doctor` and `switch` subcommands (`--help` on each) |

## Install

```sh
git clone https://github.com/eic/github-ssh-setup.git ~/.claude/skills/github-ssh-setup
```

Clone over HTTPS here, since SSH isn't set up yet. To update later: `git -C ~/.claude/skills/github-ssh-setup pull`.

Claude Code picks the skill up in the next session. Ask something like "set up SSH for GitHub", or type `/github-ssh-setup`. To work by hand, follow the steps below. They call the script as `github_ssh.py`, meaning `python3 ~/.claude/skills/github-ssh-setup/scripts/github_ssh.py`.

## How it works

`github_ssh.py config` adds this block to `~/.ssh/config`:

```
Host github.com
  User git
  IdentityAgent ~/.ssh/agent.%L.sock
  IdentityFile ~/.ssh/id_ed25519
  AddKeysToAgent yes
```

`IdentityAgent` tells ssh (and so git) where the agent socket is, with `%L` standing for the short host name. ssh reads it from this file, so no shell startup file has to set `SSH_AUTH_SOCK`. The block applies to `github.com` only, so ssh to other hosts is unaffected.

## 1. Generate a key (one time)

```sh
ssh-keygen -t ed25519 -C "<your email>" -f ~/.ssh/id_ed25519
```

Set a passphrase when asked. On clusters with a shared home directory, every host sees the same key.

## 2. Add the public key to GitHub (one time)

1. Print it: `cat ~/.ssh/id_ed25519.pub`
2. GitHub → Settings → SSH and GPG keys → **New SSH key**. Key type: *Authentication Key*. Paste the line and save.
3. If an organization (e.g. `eic`, `BNLNPPS`) uses SSO, click **Configure SSO** next to the key and authorize it for that org.

Or with the GitHub CLI: `gh ssh-key add ~/.ssh/id_ed25519.pub --title "<host>"`.

## 3. Configure ssh and load the key

```sh
github_ssh.py config -n   # preview the ~/.ssh/config change
github_ssh.py config      # write it (once per home directory)
github_ssh.py add         # start the agent if needed, enter passphrase
```

Run `add` in an interactive terminal, because it asks for the passphrase. The agent keeps running until the host reboots or it is killed; logging out does not stop it. After a reboot, or the first time on another host, run `add` again. `add --hours 8` unloads the key after 8 hours.

If you skip `add`, `AddKeysToAgent yes` still loads the key on the first `git push` or `fetch` that asks for the passphrase, provided an agent is already running.

## 4. Check

```sh
github_ssh.py doctor
```

It checks the key, the config block, the agent, the loaded key, and GitHub authentication, and prints the fix for anything that fails.

| Message | Meaning |
|---|---|
| `Permission denied (publickey)` with the key loaded | The key isn't on GitHub (step 2) |
| `ssh_askpass: ... No such file` | `ssh-add` ran without a terminal; run `add` in an interactive shell |
| Push to an org repo refused, `doctor` all ok | Key not authorized for that org's SSO (step 2.3) |

## 5. Switch existing HTTPS clones to SSH

This step is only for repos that were cloned over HTTPS. To check one, run `git remote -v`: an `https://github.com/...` URL needs switching; a `git@github.com:...` URL is already SSH and needs nothing. For new repos, clone over SSH from the start: `git clone git@github.com:<owner>/<repo>.git`.

To switch every HTTPS clone under a directory at once:

```sh
github_ssh.py switch -n /path/to/repos   # dry run: show what would change
github_ssh.py switch    /path/to/repos   # apply
```

| Option | Meaning |
|---|---|
| `--depth N` | How many directory levels below the directory to look for repos (default 4). `/path/to/repos/group/project/.git` is 3 levels down |
| `--all` | Switch every remote (e.g. `upstream`), not just `origin` |

Don't put tokens in remote URLs (`https://user:ghp_...@github.com/...`). They end up in plain text in `.git/config`. `switch` masks any it finds and flags them; revoke those at github.com/settings/tokens.

## Windows

Skip `config` and `add`. Use the built-in agent service instead (PowerShell as admin):

```powershell
Get-Service ssh-agent | Set-Service -StartupType Automatic; Start-Service ssh-agent
ssh-add $env:USERPROFILE\.ssh\id_ed25519
```

`doctor` and `switch` work as on Linux.
