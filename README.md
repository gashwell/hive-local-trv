# Hive Local TRV

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)

A Home Assistant custom integration for **Hive radiator valves (UK7004240 / TRV001)** operating entirely locally via Zigbee2MQTT and MQTT. No Hive cloud, no subscription, no internet dependency.

---

## Why this integration?

The official Hive integration is cloud-dependent and polling-based (30-second minimum). This integration:

- Operates **entirely locally** — all communication is MQTT via your own broker
- Is **event-driven** — state updates arrive instantly via Z2M push
- Implements a **full mode state machine** (off / manual / schedule / boost / away / holiday) in HA rather than relying on TRV firmware schedules
- Supports **room grouping** — aggregate multiple TRVs and temperature sensors into a single virtual climate entity
- Drives the **boiler/receiver automatically** based on aggregate heat demand from all TRVs
- Implements **geofencing** via HA person entities and **holiday mode** with automatic restore

---

## Requirements

| Requirement | Notes |
|---|---|
| Home Assistant 2024.1+ | Uses `ClimateEntityFeature.TURN_ON/OFF` added in 2024.1 |
| Zigbee2MQTT running | Any version with UK7004240 support (Z2M ≥ 1.30) |
| MQTT broker (Mosquitto) | Must be configured in HA as the MQTT integration |
| Hive TRVs (UK7004240) | Already paired to Z2M — this integration does not pair devices |
| HA Companion app (optional) | Required for geofencing via person entities |

---

## Installation

### Via HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/gashwell/hive-local-trv` as type **Integration**
3. Find **Hive Local TRV** and install
4. Restart Home Assistant

### Manual

1. Download or clone this repository
2. Copy `custom_components/hive_local_trv/` into your HA `config/custom_components/` directory
3. Restart Home Assistant

### Directory structure after installation

```
config/
  custom_components/
    hive_local_trv/
      __init__.py
      climate.py
      coordinator.py
      ...
  configuration.yaml
```

---

## Setup

After restart, go to **Settings → Integrations → Add Integration** and search for **Hive Local TRV**.

### Configuration fields

| Field | Required | Description |
|---|---|---|
| **Zigbee2MQTT base topic** | Yes | The MQTT prefix Z2M publishes on. Default: `zigbee2mqtt`. Must match your Z2M `base_topic` setting. |
| **Boiler / receiver entity** | No | The HA entity that controls your boiler (climate, switch, or input_boolean). Used to turn heat on/off and to set `heat_available` on TRVs. |
| **People to track** | No | One or more `person.*` entities for geofencing. When all selected persons leave home, heating drops to frost protection. |

### Options (reconfigurable after setup)

The boiler entity and person entities can be changed at any time via Settings → Integrations → Hive Local TRV → Configure.

---

## How discovery works

On startup the integration subscribes to `{base}/bridge/devices`. Zigbee2MQTT publishes this topic automatically whenever its device list changes (device joined, removed, renamed, interview completed).

Additionally, every **30 seconds** the integration sends a request to `{base}/bridge/request/devices` as a safety net, covering edge cases where HA restarted and missed the initial push.

Any device whose Z2M `definition.model` is `UK7004240` or `TRV001` gets a full set of entities created. If a TRV is later removed from Z2M, all its entities are automatically removed from HA.

---

## Entities created per TRV

Each discovered TRV creates a device in HA with the following entities:

| Platform | Entity | Description |
|---|---|---|
| `climate` | *(device name)* | Main control entity — temperature, mode, boost |
| `sensor` | Battery | Battery percentage |
| `sensor` | Heating Demand | PI heating demand 0–100% |
| `button` | Run Adaptation | Trigger valve calibration routine |
| `button` | Enter Mounting Mode | Re-enter calibration mode after re-fitting |
| `number` | Setpoint Offset | Fine-tune temperature offset ±2.5°C |
| `number` | Algorithm Scale Factor | PID aggressiveness 1–10 (hidden by default) |
| `number` | Boost Temperature | Default boost temperature for this TRV |
| `number` | Boost Duration | Default boost duration in minutes |
| `select` | Keypad Lock | Physical button lockout |

---

## Operating modes

The integration implements a mode state machine **in HA**, not on the TRV firmware. The TRV is always kept in `programming_operation_mode: setpoint` — HA is always in control of the target temperature.

| Mode | Description | HVAC state shown |
|---|---|---|
| `off` | Setpoint dropped to 7°C (frost protection) | `off` |
| `manual` | Fixed setpoint from the temperature slider | `heat` |
| `schedule` | Weekly schedule managed by HA, applied via setpoint pushes | `heat` |
| `boost` | Timed override at boost temperature; restores previous mode on expiry | `heat` |
| `away` | All TRVs at frost protection while all tracked persons are away | `off` |
| `holiday` | Date-range frost protection with automatic restore on return | `off` |

### Changing mode

Use the climate entity's **preset selector** in the HA UI, or set HVAC mode to `off`/`heat`.

- Preset `manual` → holds at current setpoint
- Preset `schedule` → HA-managed weekly schedule (set via `set_schedule` service)
- Preset `boost` → starts boost at configured defaults
- HVAC mode `off` → frost protection

---

## Services

All services are available in **Developer Tools → Services** and can be called from automations.

### `hive_local_trv.boost`

Start a timed boost on a TRV or room group.

```yaml
service: hive_local_trv.boost
data:
  entity_id: climate.living_room_trv
  temperature: 22        # °C — optional, uses stored default if omitted
  duration: 60           # minutes — optional, uses stored default if omitted
```

When the timer expires, the TRV automatically returns to the mode it was in before boosting.

---

### `hive_local_trv.end_boost`

Cancel an active boost immediately and restore the previous mode.

```yaml
service: hive_local_trv.end_boost
data:
  entity_id: climate.living_room_trv
```

---

### `hive_local_trv.set_schedule`

Set a weekly heating schedule for a TRV or room group. The schedule is stored persistently and survives HA restarts.

Days: `0` = Monday … `6` = Sunday.

```yaml
service: hive_local_trv.set_schedule
data:
  entity_id: climate.living_room_trv
  schedule:
    - days: [0, 1, 2, 3, 4]    # Mon–Fri
      time: "06:30"
      temperature: 20.5
    - days: [0, 1, 2, 3, 4]
      time: "08:30"
      temperature: 18.0
    - days: [0, 1, 2, 3, 4]
      time: "17:00"
      temperature: 21.0
    - days: [0, 1, 2, 3, 4]
      time: "22:00"
      temperature: 17.0
    - days: [5, 6]              # Sat–Sun
      time: "07:30"
      temperature: 21.0
    - days: [5, 6]
      time: "23:00"
      temperature: 17.0
```

On startup the integration applies whichever slot is currently active and schedules the next transition. Schedules are persisted to HA's `.storage` directory.

---

### `hive_local_trv.advance_schedule`

Skip to the next scheduled slot immediately — equivalent to Hive's "advance" button. Useful if you're going to bed early or leaving the house before the next scheduled drop.

```yaml
service: hive_local_trv.advance_schedule
data:
  entity_id: climate.living_room_trv
```

---

### `hive_local_trv.clear_schedule`

Remove the schedule from a TRV or room group. The TRV stays in its current mode at the last temperature until the mode is changed.

```yaml
service: hive_local_trv.clear_schedule
data:
  entity_id: climate.living_room_trv
```

---

### `hive_local_trv.set_holiday`

Activate frost protection for a date range. All TRVs and room groups drop to 7°C on departure and automatically restore their previous modes on return.

The holiday state persists across HA restarts — if HA restarts mid-holiday, the return timer is re-armed correctly.

```yaml
service: hive_local_trv.set_holiday
data:
  departure: "2025-08-01T09:00:00"    # ISO 8601
  return: "2025-08-14T18:00:00"
```

If `departure` is in the past, holiday mode activates immediately.

---

### `hive_local_trv.cancel_holiday`

Cancel an active or pending holiday and immediately restore all TRV modes.

```yaml
service: hive_local_trv.cancel_holiday
```

---

### `hive_local_trv.add_room`

Create a virtual room group. The room appears as a single climate entity with averaged temperature from all member TRVs and any additional sensors.

```yaml
service: hive_local_trv.add_room
data:
  room_name: "Living Room"
  trv_entity_ids:
    - lounge_trv_1          # Z2M friendly names, not HA entity IDs
    - lounge_trv_2
  temp_sensor_entity_ids:   # HA sensor entity IDs — optional
    - sensor.lounge_aqara_temperature
    - sensor.lounge_sonoff_temperature
```

Room temperature is the **average of all sources** — both TRV local sensors and any additional temperature sensors. No source is preferred over another. Any source that is unavailable or unparseable is excluded from the average.

Commands sent to a room group (set temperature, change mode, boost, schedule) are fanned out to all member TRVs simultaneously.

Room groups persist across HA restarts.

---

### `hive_local_trv.remove_room`

Remove a room group. The individual TRV entities remain; only the virtual room climate entity is deleted.

```yaml
service: hive_local_trv.remove_room
data:
  room_name: "Living Room"
```

---

## Boiler / receiver demand management

When a boiler entity is configured, the integration automatically controls it based on aggregate `heat_required` from all TRVs and room groups.

- When **any** TRV or room reports `heat_required: true` → boiler entity is turned on
- When **all** TRVs and rooms report `heat_required: false` → boiler entity is turned off

The integration also sends `heat_available: true/false` to all TRVs whenever the boiler state changes. This allows TRV firmware to optimise its PID behaviour — when heat is unavailable the TRV won't over-open the valve trying to compensate.

### Supported boiler entity domains

| Domain | Action used |
|---|---|
| `climate` | `set_hvac_mode` with `heat` / `off` |
| `switch` | `turn_on` / `turn_off` |
| `input_boolean` | `turn_on` / `turn_off` |

---

## Geofencing

Configure `person.*` entities during integration setup or via the options flow. The integration watches state changes on all configured person entities.

- When **all** tracked persons are **not** in the `home` state → away mode activates (all TRVs at frost protection), current modes are saved
- When **any** tracked person returns to `home` → previous modes are restored

Away mode is lower priority than holiday mode. If a holiday is active, arriving home does not cancel it.

The person entities are populated automatically by the HA Companion app when location tracking is enabled on your phone.

---

## Geofencing automation example

You can also implement custom geofencing logic using the existing services:

```yaml
alias: Heating away mode
trigger:
  - platform: state
    entity_id: person.gary
    to: "not_home"
condition:
  - condition: state
    entity_id: person.gary
    state: "not_home"
action:
  - service: hive_local_trv.set_holiday
    data:
      departure: "{{ now().isoformat() }}"
      return: "{{ (now() + timedelta(hours=8)).isoformat() }}"
```

---

## External temperature sensor

TRV temperature sensors sit next to a hot radiator pipe and read 5–8°C higher than actual room temperature. For best accuracy, push a room temperature from a separate sensor using an automation:

```yaml
alias: Push room temp to TRV
trigger:
  - platform: state
    entity_id: sensor.living_room_temperature
  - platform: time_pattern
    minutes: "/30"    # heartbeat — TRV disables external sensor after 3 hours
action:
  - service: mqtt.publish
    data:
      topic: zigbee2mqtt/living_room_trv/set
      payload: >
        {"external_measured_room_sensor":
          {{ (states('sensor.living_room_temperature') | float * 100) | int }} }
```

Note: Z2M expects the value in units of 0.01°C (21°C → send `2100`).

If you use room groups, adding a temperature sensor to the group is simpler — the averaging logic handles it automatically.

---

## First-time setup checklist

After installing and configuring the integration:

1. **Wait for discovery** — TRVs appear within 30 seconds once Z2M sends its device list
2. **Run Adaptation** — press the "Run Adaptation" button on each TRV after fitting it to its radiator valve. This calibrates the valve spring force and travel distance. Takes ~5 minutes per TRV
3. **Set programming mode** — the integration sets `programming_operation_mode: setpoint` automatically on discovery, but verify in the Z2M exposes tab if you see unexpected behaviour
4. **Set schedules** — use `set_schedule` to push your weekly heating programme
5. **Configure rooms** — use `add_room` to group TRVs in the same room

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| TRVs not discovered | Z2M base topic mismatch | Check Z2M config for `base_topic` value |
| TRVs not discovered | TRV not paired to Z2M | Pair the TRV to Z2M first using Z2M's permit-join |
| Temperature stuck at 7°C | Away or holiday mode active | Check `mode` attribute on climate entity |
| Boiler not firing | No boiler entity configured | Set boiler entity in options flow |
| Boiler stays on | heat_required never false | Check `heat_required` attribute; may be a Z2M connectivity issue |
| Schedule not applying | TRV in wrong mode | Set preset to `schedule` |
| "Configure failed" errors in Z2M log | Known harmless Danfoss attribute issue | Safe to ignore; device still works |

---

## Known limitations

- **No OTA firmware updates** — Hive firmware rejects Danfoss OTA images. TRV firmware cannot be upgraded through Z2M
- **`radiator_covered` not functional** — Hive firmware returns `UNSUPPORTED_ATTRIBUTE` for this Danfoss feature. TRVs always operate in Auto Offset mode rather than Room Sensor mode
- **Setpoint cap at 32°C** — Hive firmware hard-caps the setpoint; Danfoss hardware supports 35°C
- **No OpenTherm modulation** — boiler control is on/off only; no flow temperature control

---

## Further reading

- [File reference](docs/file-reference.md) — documentation for every source file
- [Architecture](docs/architecture.md) — data flow diagrams and component overview
- [Zigbee2MQTT UK7004240 device page](https://www.zigbee2mqtt.io/devices/UK7004240.html)

---

## License

MIT
