<p align="center">
  <img src="fritzBoxProfileManager.png" alt="FritzBox Profile Manager" width="180"/>
</p>

# FritzBox Profile Manager

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Version](https://img.shields.io/github/v/release/frcarlo/ha-fritz-profiles)](https://github.com/frcarlo/ha-fritz-profiles/releases)

Home Assistant Custom Integration zur Verwaltung von FritzBox Kindersicherungs-Profilen direkt aus HA heraus — ohne sich in die FritzBox-Oberfläche einzuloggen.

## Features

- **Profil wechseln** — Select-Entity pro Gerät: beliebiges Zugangsprofil zuweisen (Standard, Kids, Gesperrt, …)
- **Internet sperren/freigeben** — Switch-Entity pro Gerät: schneller Toggle
- **Verbleibende Zeit** — Attribut `time_remaining_minutes` zeigt das restliche Zeitbudget pro Gerät
- **Tickets anzeigen** — Sensor mit verfügbaren 45-Minuten-Ticket-Codes als Attribut
- **Tickets zurücksetzen** — Button zum Generieren neuer Ticket-Codes

## Voraussetzungen

- FRITZ!Box mit FritzOS ≥ 7.24
- FritzBox-Benutzer mit Berechtigung für Kindersicherung
- [HACS](https://hacs.xyz) installiert

## Installation via HACS

1. HACS → **⋮ → Custom repositories**
2. URL: `https://github.com/frcarlo/ha-fritz-profiles`
3. Kategorie: **Integration** → Hinzufügen
4. Integration suchen und installieren
5. Home Assistant neu starten

## Einrichtung

**Einstellungen → Integrationen → + Hinzufügen → "FritzBox Profile Manager"**

| Feld | Beispiel |
|------|---------|
| Host | `fritz.box` oder `192.168.178.1` |
| Benutzername | FritzBox-Benutzername |
| Passwort | FritzBox-Passwort |

## Entities

### Pro Netzwerkgerät
| Entity | Typ | Beschreibung |
|--------|-----|-------------|
| `select.GERÄT_profil` | Select | Zugangsprofil auswählen |
| `switch.GERÄT_internet` | Switch | Internet sperren / freigeben |

Beide Entities haben das Attribut `time_remaining_minutes` (Minuten verbleibend) — nur gesetzt wenn das Gerät ein Zeitbudget hat.

### Global (FritzBox Profile Manager Gerät)
| Entity | Typ | Beschreibung |
|--------|-----|-------------|
| `sensor.fritzbox_profile_manager_verfugbare_tickets` | Sensor | Anzahl verfügbarer Tickets + Codes als Attribut |
| `button.fritzbox_profile_manager_tickets_zurucksetzen` | Button | Neue Ticket-Codes generieren |

### Ticket-Codes auf dem Dashboard anzeigen

Markdown-Karte:
```yaml
type: markdown
title: Ticket Codes
content: >
  **{{ state_attr('sensor.fritzbox_profile_manager_verfugbare_tickets', 'available_codes') | length }} von {{ state_attr('sensor.fritzbox_profile_manager_verfugbare_tickets', 'total') }} verfügbar**

  {% set codes = state_attr('sensor.fritzbox_profile_manager_verfugbare_tickets', 'available_codes') %}
  {% for code in codes %}
  🎟️ {{ code }}
  {% endfor %}
```

### Ticket einlösen (für Kinder)

Wenn das Zeitbudget aufgebraucht ist, einfach im Browser auf dem Gerät aufrufen:
```
http://fritz.box/internet/kids_ticket.lua
```

## Beispiel-Automatisierungen

```yaml
# Abends Kinder-Internet sperren
automation:
  - alias: "Kinder-Internet abends sperren"
    trigger:
      platform: time
      at: "21:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.redmi_pad_se_profil
        data:
          option: "Kids"

  - alias: "Kinder-Internet morgens freigeben"
    trigger:
      platform: time
      at: "07:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.redmi_pad_se_profil
        data:
          option: "Standard"

  - alias: "Benachrichtigung wenn noch 10 Minuten übrig"
    trigger:
      platform: numeric_state
      entity_id: select.redmi_pad_se_profil
      attribute: time_remaining_minutes
      below: 10
    action:
      - service: notify.mobile_app
        data:
          message: "Noch 10 Minuten Online-Zeit!"
```

## Technische Details

Die Integration nutzt die interne FritzBox LUA API (`/data.lua`) mit PBKDF2-SHA256 Authentifizierung. Kein externes Python-Paket nötig — nur `aiohttp` (bereits in Home Assistant enthalten).

| Seite | Inhalt |
|-------|--------|
| `kidPro` | Ticket-Codes (HTML-Parsing) |
| `kidLis` | Geräteliste mit Profilen und Zeitbudgets (HTML-Parsing) |
| `/internet/kids_userlist.lua` | Profil setzen (POST) |
| `/internet/kids_profilelist.lua` | Tickets zurücksetzen (POST) |

**Hinweis:** Die FritzBox weist Geräten bei jedem Profilwechsel neue interne UIDs zu. Die Integration erkennt Geräte daher zusätzlich über den Gerätenamen als Fallback.
