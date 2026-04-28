<p align="center">
  <img src="fritzBoxProfileManager.png" alt="FritzBox Profile Manager" width="180"/>
</p>

# FritzBox Profile Manager

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Version](https://img.shields.io/github/v/release/frcarlo/ha-fritz-profiles)](https://github.com/frcarlo/ha-fritz-profiles/releases)

Home Assistant custom integration for managing FritzBox parental control profiles — without logging into the FritzBox interface.

## Features

- **Switch profiles** — Select entity per device: assign any access profile (Standard, Kids, Blocked, …)
- **Block / unblock internet** — Switch entity per device: quick toggle
- **Remaining time** — `time_remaining_minutes` attribute shows the remaining daily time budget per device
- **Ticket codes** — Sensor with available 45-minute online-time ticket codes as attributes
- **Reset tickets** — Button to generate a new set of ticket codes

## Requirements

- FRITZ!Box with FritzOS ≥ 7.24
- FritzBox user account with parental control permission
- [HACS](https://hacs.xyz) installed

## Installation via HACS

1. HACS → **⋮ → Custom repositories**
2. URL: `https://github.com/frcarlo/ha-fritz-profiles`
3. Category: **Integration** → Add
4. Search for the integration and install it
5. Restart Home Assistant

## Setup

**Settings → Integrations → + Add Integration → "FritzBox Profile Manager"**

| Field | Example |
|-------|---------|
| Host | `fritz.box` or `192.168.178.1` |
| Username | FritzBox username |
| Password | FritzBox password |

## Entities

### Per network device
| Entity | Type | Description |
|--------|------|-------------|
| `select.DEVICE_profil` | Select | Choose access profile |
| `switch.DEVICE_internet` | Switch | Block / unblock internet |

Both entities expose the attribute `time_remaining_minutes` (minutes left today) — only set when the device has a daily time budget.

### Global (FritzBox Profile Manager device)
| Entity | Type | Description |
|--------|------|-------------|
| `sensor.fritzbox_profile_manager_verfugbare_tickets` | Sensor | Number of available tickets + codes as attribute |
| `button.fritzbox_profile_manager_tickets_zurucksetzen` | Button | Generate new ticket codes |

### Show ticket codes on the dashboard

Markdown card:
```yaml
type: markdown
title: Ticket Codes
content: >
  **{{ state_attr('sensor.fritzbox_profile_manager_verfugbare_tickets', 'available_codes') | length }} of {{ state_attr('sensor.fritzbox_profile_manager_verfugbare_tickets', 'total') }} available**

  {% set codes = state_attr('sensor.fritzbox_profile_manager_verfugbare_tickets', 'available_codes') %}
  {% for code in codes %}
  🎟️ {{ code }}
  {% endfor %}
```

### Redeeming a ticket (for kids)

When the daily time budget runs out, open this URL in the browser on the device:
```
http://fritz.box/internet/kids_ticket.lua
```

## Example automations

```yaml
# Block kids' internet in the evening
automation:
  - alias: "Block kids internet at night"
    trigger:
      platform: time
      at: "21:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.redmi_pad_se_profil
        data:
          option: "Kids"

  - alias: "Unblock kids internet in the morning"
    trigger:
      platform: time
      at: "07:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.redmi_pad_se_profil
        data:
          option: "Standard"

  - alias: "Notify when 10 minutes of online time left"
    trigger:
      platform: numeric_state
      entity_id: select.redmi_pad_se_profil
      attribute: time_remaining_minutes
      below: 10
    action:
      - service: notify.mobile_app
        data:
          message: "Only 10 minutes of online time left!"
```

## Technical details

The integration uses the internal FritzBox LUA API (`/data.lua`) with PBKDF2-SHA256 authentication. No external Python packages required — only `aiohttp` which is already bundled with Home Assistant.

| Page | Content |
|------|---------|
| `kidPro` | Ticket codes (HTML parsing) |
| `kidLis` | Device list with profiles and time budgets (HTML parsing) |
| `/internet/kids_userlist.lua` | Set profile (POST) |
| `/internet/kids_profilelist.lua` | Reset tickets (POST) |

**Note:** The FritzBox reassigns internal device UIDs on every profile change. The integration therefore identifies devices by name as a fallback to ensure entities remain stable across profile switches.
