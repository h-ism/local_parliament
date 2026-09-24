# Unattended units

What keeps the two long-running things going when nobody is logged in. Copied
here so they are reproducible; systemd reads them from `~/.config/systemd/user/`.

```bash
cp scripts/systemd/pt-*.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now pt-ssp-collect.timer pt-voices-recon.timer pt-voices-collect.timer
loginctl enable-linger "$USER"     # or they stop when you log out
```

| unit | what it does |
| --- | --- |
| `pt-ssp-collect` | Runs `collect_ssp.sh small`. The timer is a **watchdog**, not a schedule: every 20 minutes it starts the script, which takes a `flock`, skips finished tenants and exits at once when the set is done. A fire that is not needed costs nothing and no request. |
| `pt-voices-recon` | Runs `recon_sites.py` at **Sat/Sun 20:00**, which is the only time 滋賀 and 石川 agreed to. `PoliteClient` carries the window too, so even a misfiring timer fetches nothing outside it. |
| `pt-voices-collect` | Runs `collect_voices.sh` on the same evenings. It collects a site only once three things hold: October has started (石川 sits until 2026-09-30), a config exists in `sites/` (so somebody has read the markup), and the window is open. Each condition prints what is missing instead of failing quietly. |

Two things this is guarding against, both of which have happened to crawls
before: a run that dies overnight and is noticed three days later, and *two*
runs that quietly halve the interval an operator was promised. The lock is the
second guard; `Persistent=true` and `OnBootSec` are the first.

Stopping everything:

```bash
systemctl --user stop pt-ssp-collect.timer pt-ssp-collect.service
systemctl --user stop pt-voices-recon.timer pt-voices-collect.timer
```
