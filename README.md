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

