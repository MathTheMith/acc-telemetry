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

