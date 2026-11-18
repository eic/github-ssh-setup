# github-ssh-setup

Set up git over SSH to GitHub, check that it works, and switch existing HTTPS clones to SSH. Everything runs from one Python script (`scripts/github_ssh.py`; Python 3.6+, standard library only). It works the same from bash, zsh or tcsh, on Linux and macOS.

It is also a [Claude Code](https://claude.com/claude-code) skill. Once installed, you can ask Claude to set up SSH, find out why a push fails, or switch your repos.

## Quick start

```sh
git clone https://github.com/eic/github-ssh-setup.git ~/.claude/skills/github-ssh-setup
cd ~/.claude/skills/github-ssh-setup

ssh-keygen -t ed25519 -C "<your email>"   # skip if ~/.ssh/id_ed25519 exists
# add ~/.ssh/id_ed25519.pub at https://github.com/settings/keys  (step 2)
python3 scripts/github_ssh.py config       # point ssh at a per-host agent
python3 scripts/github_ssh.py add          # start agent, enter passphrase
python3 scripts/github_ssh.py doctor       # everything should say "ok"
```

Clone over HTTPS, as above, since SSH isn't set up yet. Without Claude Code, you can clone the repo anywhere. To update later, run `git pull` in the clone.

All commands below run from the clone's directory.

## 1. Generate a key (one time)

```sh
ssh-keygen -t ed25519 -C "<your email>" -f ~/.ssh/id_ed25519
```

Set a passphrase when asked. On clusters with a shared home directory, every host sees the same key.

## 2. Add the public key to GitHub (one time)

1. Print it: `cat ~/.ssh/id_ed25519.pub`
2. GitHub → Settings → SSH and GPG keys → **New SSH key**. Key type: *Authentication Key*. Paste the line and save.
3. If an organization (e.g. `eic`, `BNLNPPS`) uses SAML SSO, click **Configure SSO** next to the key and authorize it for that org.

Or with the GitHub CLI: `gh ssh-key add ~/.ssh/id_ed25519.pub --title "<host>"`.

## 3. Configure ssh and load the key

```sh
python3 scripts/github_ssh.py config -n   # preview the ~/.ssh/config change
python3 scripts/github_ssh.py config      # write it (once per home directory)
python3 scripts/github_ssh.py add         # start the agent if needed, enter passphrase
```

If `~/.ssh/config` already has a `Host github.com` entry, `config` leaves the file alone and prints the lines to merge in by hand.

Run `add` in an interactive terminal, because it asks for the passphrase. The agent keeps running until the host reboots or it is killed; logging out does not stop it. After a reboot, or the first time on another host, run `add` again. `add --hours 8` unloads the key after 8 hours.

For a key other than `~/.ssh/id_ed25519`, pass `--key PATH` to `config`, `add` and `doctor`.

## 4. Check

```sh
python3 scripts/github_ssh.py doctor
```

It checks the key, the config block, the agent, the loaded key and GitHub authentication, and prints the fix for anything that fails.

| Symptom | Cause |
|---|---|
| `Permission denied (publickey)` with the key loaded | The key isn't on GitHub (step 2) |
| `ssh_askpass: ... No such file` | `ssh-add` ran without a terminal; run `add` in an interactive shell |
| Push to an org repo refused, `doctor` all ok | Key not authorized for that org's SSO (step 2.3) |

## 5. Switch existing HTTPS clones to SSH

This step is only for repos that were cloned over HTTPS. To check one, run `git remote -v`: an `https://github.com/...` URL needs switching; a `git@github.com:...` URL is already SSH and needs nothing. For new repos, clone over SSH from the start: `git clone git@github.com:<owner>/<repo>.git`.

To switch every HTTPS clone under a directory at once:

```sh
python3 scripts/github_ssh.py switch -n /path/to/repos   # dry run: show what would change
python3 scripts/github_ssh.py switch    /path/to/repos   # apply
```

| Option | Meaning |
|---|---|
| `--depth N` | How many directory levels below the directory to look for repos (default 4). `/path/to/repos/group/project/.git` is 3 levels down |
| `--all` | Switch every remote (e.g. `upstream`), not just `origin` |

Don't put tokens in remote URLs (`https://user:ghp_...@github.com/...`). They end up in plain text in `.git/config`. `switch` masks any it finds and flags them; revoke those at https://github.com/settings/tokens.

## How it works

`config` adds this block at the top of `~/.ssh/config`:

```
# managed by github_ssh.py
Host github.com
  User git
  IdentityAgent ~/.ssh/agent.%L.sock
  IdentityFile ~/.ssh/id_ed25519
  AddKeysToAgent yes
```

`IdentityAgent` tells ssh, and so git, where the agent socket is; `%L` is the short host name. ssh reads this from its config file, so no shell startup file needs to set `SSH_AUTH_SOCK`. The block applies only to `github.com`.

`add` starts `ssh-agent -a ~/.ssh/agent.<host>.sock` if nothing answers on that socket, then runs `ssh-add`.

To undo: delete the block from `~/.ssh/config`, and stop the agent with `pkill -f 'ssh-agent -a .*agent\.'"$(hostname -s)"'\.sock'`.

## Windows

Skip `config` and `add`. Use the built-in agent service instead (PowerShell as admin):

```powershell
Get-Service ssh-agent | Set-Service -StartupType Automatic; Start-Service ssh-agent
ssh-add $env:USERPROFILE\.ssh\id_ed25519
```

`doctor` and `switch` work as on Linux.

## Using it with Claude Code

Cloned into `~/.claude/skills/github-ssh-setup`, the skill loads in new Claude Code sessions. Invoke it with `/github-ssh-setup`, or ask in plain words ("my git push says permission denied"). `SKILL.md` holds Claude's instructions. Claude runs `doctor`, `config` and `switch` itself, after showing you a dry run. It leaves steps that need your passphrase (`ssh-keygen`, `add`) to you.
