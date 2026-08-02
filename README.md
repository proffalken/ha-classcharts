# ClassCharts (Parent) for Home Assistant

An unofficial Home Assistant custom integration for the [ClassCharts](https://www.classcharts.com/) Parent
portal. Exposes rewards/behaviour totals and today's timetable as sensors, per student.

This uses ClassCharts' undocumented parent API and is not affiliated with or endorsed by
ClassCharts / Tes Global.

## Features

- Sign in with your ClassCharts Parent email/password via the HA config flow
- Per-student sensors:
  - Total positive / negative behaviour points
  - One sensor per reward/behaviour reason
  - Today's timetable (lesson count + lesson details as attributes)
- Configurable daily timetable refresh hour (local time)

## Installation

### HACS (custom repository)

1. In HACS, add this repository as a custom repository (category: Integration).
2. Install "ClassCharts (Parent)".
3. Restart Home Assistant.

### Manual

Copy `custom_components/classcharts` into your Home Assistant `config/custom_components/` directory
and restart Home Assistant.

## Setup

Settings → Devices & Services → Add Integration → "ClassCharts (Parent)", then sign in and pick a
student.

## Known limitations

ClassCharts' login endpoint expects a recaptcha token that this integration cannot solve headlessly.
If ClassCharts tightens recaptcha enforcement, login may start failing; if that happens the
integration will surface a reauthentication prompt in Home Assistant rather than failing silently.

## Development

```bash
uv venv
uv pip install -e ".[test]"
pytest
```

See `.github/workflows/test.yml` for CI (pytest + HACS/hassfest validation).
