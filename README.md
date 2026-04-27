# FritzBox Profile Manager

Home Assistant Custom Integration zur Verwaltung von FritzBox Kindersicherungs-Profilen.

## Features

- **Profil wechseln** — Select-Entity pro Gerät: beliebiges Zugangsprofil zuweisen
- **Internet sperren/freigeben** — Switch-Entity pro Gerät: schneller Toggle zwischen Standard und Gesperrt
- **Tickets anzeigen** — Sensor mit allen verfügbaren 45-Minuten-Tickets (Codes als Attribute)
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

### Global
| Entity | Typ | Beschreibung |
|--------|-----|-------------|
| `sensor.fritzbox_verfugbare_tickets` | Sensor | Anzahl verfügbarer Tickets, Codes als Attribut |
| `button.fritzbox_tickets_zurucksetzen` | Button | Neue Ticket-Codes generieren |

## Beispiel-Automation

```yaml
# Abends Kindersicherung aktivieren
automation:
  - alias: "Kinder-Internet abends sperren"
    trigger:
      platform: time
      at: "21:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.galaxy_tab_a8_profil
        data:
          option: "Gesperrt"

  - alias: "Kinder-Internet morgens freigeben"
    trigger:
      platform: time
      at: "07:00:00"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.galaxy_tab_a8_internet
```

## Technische Details

Die Integration nutzt die interne FritzBox LUA API (`/data.lua`) mit PBKDF2-SHA256 Authentifizierung. Kein externes Python-Paket nötig — nur `aiohttp` (bereits in Home Assistant enthalten).

| Seite | Inhalt |
|-------|--------|
| `kidPro` | Profilliste + Ticket-Codes (HTML-Parsing) |
| `kidLis` | Geräteliste mit aktuellen Profilen (HTML-Parsing) |
| `/internet/kids_userlist.lua` | Profil setzen (POST) |
| `/internet/kids_profilelist.lua` | Tickets zurücksetzen (POST) |
