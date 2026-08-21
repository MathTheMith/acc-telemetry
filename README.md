# ACC Telemetry - Trail Braking

Real-time telemetry dashboard for Assetto Corsa Competizione: live
throttle/brake curves, automatic lap splitting, and a color-coded track map
(green = throttle, red = brake) to precisely visualize trail braking, lap by
lap.

## How it works

- The program reads ACC's **Shared Memory** via the
  [`pyaccsharedmemory`](https://github.com/rrennoir/PyAccSharedMemory)
  library, which parses the structures documented by Kunos. **This only
  works on Windows, while ACC is running** (Windows Shared Memory doesn't
  exist on Linux/Mac).
- Lap splitting is automatic: it watches the normalized position on the
  track (`normalized_car_position`), and a lap ends when it wraps from
  ~1.0 back down to ~0.0. The lap time comes directly from ACC
  (`last_time`).
- Every finished lap is saved to disk immediately
  (`sessions/<date>_<circuit>/lap_XXX_....csv` + `session.json`), so
  nothing is lost even if the app crashes.
- In parallel, each lap is also sent to the web server (see next section)
  to end up in the site's database — that's what powers the dashboard you
  can browse, with history, filters by circuit/car, and lap deletion.
- No direct interface with a wheel/pedals is needed: ACC already provides
  the throttle/brake % after processing (deadzone, curve, progressive
  braking), which is exactly the data relevant for analyzing trail
  braking.

## The web site (dashboard viewable in the browser)

The dashboard (list of all laps, filterable by circuit/car, full recap on
click: time, sectors, color-coded track map, pedal/speed trace) runs in
Docker: Nginx exposes a single port and serves the site, and proxies
`/api/*` to a backend container that is never exposed directly.

```
ACC machine / another device
        │  http://<SERVER_ADDRESS>:8081
        ▼
┌────────────────────┐
│ frontend (nginx)    │  serves the dashboard (frontend/index.html)
│ port 8081 → 80      │  proxies /api/* → backend:5000 (internal Docker network)
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│ backend (Flask)      │  REST API (list/detail/delete laps)
│ 127.0.0.1:5001 only  │  NOT exposed publicly
└─────────┬────────────┘
          │
┌─────────▼────────────┐
│ SQLite (Docker volume)│
└───────────────────────┘
```

Two ways to use it:

- **Locally, on the same machine as ACC**: the simplest way to get
  started, no network configuration needed. The dashboard is available at
  `http://127.0.0.1:8081`.
- **On a remote server** (VPS, NAS, always-on PC...): useful for checking
  the dashboard from a phone or another device while you're driving. See
  "Access from another device" below.

Requires [Docker](https://www.docker.com/) and Docker Compose (`docker
compose`) installed on the machine hosting the site.

### Launch / manage the site

```bash
make up          # build + start the site in the background
make logs        # follow the logs (Ctrl+C to quit)
make ps          # container status
make down        # stop everything
make seed        # add a few demo laps (simulator) to test without ACC
make backup      # back up the SQLite database into backups/ (keeps the last 14)
make restore FILE=backups/telemetry-xxx.db   # restore
make reset       # remove everything (including the database) then restart
```

### Access from another device (optional)

If the site runs on a remote server rather than locally, open
**`http://<SERVER_ADDRESS>:8081`** from any browser. The tab refreshes
automatically every 4 seconds.

Two things to check on the server side for the port to be reachable from
outside:
1. The system firewall must allow port 8081 (`ufw allow 8081/tcp` if
   `ufw` is active).
2. If the server is on a cloud host, its security group / network
   firewall must also allow this port inbound — an open `ufw` isn't
   enough if an upstream firewall still blocks it.

### Point the Windows desktop app at the server

If the site runs locally on the same machine as ACC, there's nothing to
do: `127.0.0.1` is already the default.

If the site runs on a remote server, `acc_telemetry` needs to point to
that server instead of `127.0.0.1`. Before launching `python main.py`,
simply set:

```
set ACC_SERVER_URL=http://<SERVER_ADDRESS>:8081/api/laps
python main.py
```

Each finished lap is then sent to the server in the background. If it's
unreachable (no network, closed port...), that's fine: the lap is still
saved to CSV locally as before, only the upload to the site is missed for
that lap.

## Testing without ACC (simulator mode)

Before plugging in the wheel, you can check that everything works with a
fake driver going around a made-up circuit:

```bash
python main.py --sim
```

Each simulated lap has a different random "trail braking quality", so
you'll see the track map change shape (more or less progressive braking)
from lap to lap - a good way to check the color coding is readable before
actually driving.

## Using with ACC (Windows)

1. Install Python 3.10+ on the Windows machine running ACC.
2. In the project folder:
   ```
   pip install -r requirements.txt
   python main.py
   ```
3. Launch ACC, go on track (practice/hotlap/race). The status in the top
   right switches from "Waiting for ACC data..." to "Connected to ACC".
4. Drive: the throttle/brake curves scroll live, the track map draws live
   for the current lap.
5. At the end of each lap, it appears in the "Laps" list on the right.
   Double-click a lap to display it on the map instead of live (compared
   against the best lap shown faded in the background).

## Building the .exe (do this once, on Windows)

Double-click `build_exe.bat` (or run it from a terminal). It creates a
virtual environment, installs the dependencies, then generates
`dist\ACC_Telemetry.exe`. You can then launch that .exe directly, without
needing to reopen a Python terminal.

The `.exe` isn't included in the repo: PyInstaller compiles for the
platform it runs on, so it needs to be built once on the Windows machine
that will run the app.

