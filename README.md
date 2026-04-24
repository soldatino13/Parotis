# 🌍 PAROTIS v4 — Sprache, Stämme & Strukturen

> *"Was hast du erschaffen?"*
> Inspiriert von Black Mirror S07E04 – Plaything (2025)

Eine isometrische Lebenssimulation im **Habbo-Hotel-Stil** für Raspberry Pi mit Touchscreen.
Parotis bilden Stämme, entwickeln eine eigene Sprache, bauen Strukturen und erzeugen generative Musik.  
Jedes Wesen — ein **Paroti** — hat ein einzigartiges Genom, das Aussehen, Verhalten,  
Persönlichkeit und Nachkommen bestimmt. Du bist der Gott dieser kleinen Welt.

Die Welt wird **isometrisch (2.5D)** dargestellt: Diamant-Kachelboden, Habbo-style
Figuren mit Shirt, Hose, Kopf, Haaren und genbasierten Accessoires (Brille, Heiligenschein).

---

## Inhalt

- [Hardware](#hardware)
- [Schnellstart](#schnellstart)
- [Vollständige Installation](#vollständige-installation)
- [Desktop-Icon einrichten](#desktop-icon-einrichten)
- [Gott-Bild (dein Foto)](#gott-bild-dein-foto)
- [Das Postfach-System](#das-postfach-system)
- [Touch-Steuerung & Menü](#touch-steuerung--menü)
- [Das Genom erklärt](#das-genom-erklärt)
- [Paroti-Zustände](#paroti-zustände)
- [Evolutionsmechanik](#evolutionsmechanik)
- [Persistenz & Speicherung](#persistenz--speicherung)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)

---

## Hardware

| Komponente | Empfehlung |
|---|---|
| Board | Raspberry Pi 4 oder Pi 5 |
| Display | Offizieller 7" Pi Touchscreen, oder beliebiges HDMI-Touchdisplay |
| Betriebssystem | Raspberry Pi OS 64-bit (Desktop-Version) |
| Speicher | 16 GB SD-Karte oder grösser |
| Strom | Offizielles Pi-Netzteil (3A für Pi 4, 5A für Pi 5) |

---

## Schnellstart

Drei Befehle — direkt auf dem Pi im Terminal eingeben:

```bash
git clone https://github.com/soldatino13/Parotis.git ~/parotis
cd ~/parotis
chmod +x install.sh && ./install.sh
```

Danach: Doppelklick auf das **Parotis-Icon** auf dem Desktop. Fertig.

---

## Vollständige Installation

### 1. Repository klonen

Auf dem Pi ein Terminal öffnen und eingeben:

```bash
git clone https://github.com/soldatino13/Parotis.git ~/parotis
```

Falls `git` nicht installiert ist:

```bash
sudo apt-get install -y git
git clone https://github.com/soldatino13/Parotis.git ~/parotis
```

### 2. Installations-Skript ausführen

```bash
cd ~/parotis
chmod +x install.sh
./install.sh
```

Das Skript erledigt automatisch:

- System-Pakete installieren (`python3-pygame`, `unclutter`, etc.)
- Postfach-Verzeichnis `~/parotis-inbox/` anlegen (inkl. Willkommens-Nachricht)
- Beispiel-Befehls-Datei `BEFEHLE.txt.beispiel` erstellen
- Desktop-Icon auf `~/Desktop/Parotis.desktop` kopieren
- Programm-Icon (`icon.png`) generieren
- Start-Skript `~/parotis/start.sh` anlegen

### 3. Manuell (ohne install.sh)

Falls du lieber alles von Hand machst:

```bash
# Repository klonen
git clone https://github.com/soldatino13/Parotis.git ~/parotis

# Abhängigkeiten
sudo apt-get update
sudo apt-get install -y python3-pygame unclutter x11-xserver-utils

# Datenverzeichnis
mkdir -p ~/.parotis

# Postfach
mkdir -p ~/parotis-inbox/gelesen

# Starten
cd ~/parotis
python3 parotis.py
```

### Updates einspielen

Wenn eine neue Version auf GitHub verfügbar ist:

```bash
cd ~/parotis
git pull
```

---

## Desktop-Icon einrichten

Nach `install.sh` liegt `Parotis.desktop` bereits auf dem Desktop.

**Falls es nicht klappbar/ausführbar ist** (LXDE auf Pi OS):

```bash
# Rechtsklick auf das Icon → "Als vertrauenswürdig markieren"
# Oder per Terminal:
chmod +x ~/Desktop/Parotis.desktop
gio set ~/Desktop/Parotis.desktop metadata::trusted true
```

**Autostart beim Booten** (optional):

```bash
mkdir -p ~/.config/autostart
cp ~/Desktop/Parotis.desktop ~/.config/autostart/
```

---

## Gott-Bild (dein Foto)

Die Parotis verehren (oder fürchten) dich als Gott. Dein Foto erscheint als Schrein auf dem Spielfeld.

### Foto einrichten

Lege dein Bild in das Postfach-Verzeichnis:

```
~/parotis-inbox/god.jpg    ← bevorzugt
~/parotis-inbox/god.png    ← alternativ
~/parotis-inbox/god.bmp    ← alternativ
```

Das Bild wird automatisch auf **96×96 Pixel** skaliert. Ein Quadrat-Ausschnitt (Gesicht) funktioniert am besten.

**Ohne Foto:** Es erscheint automatisch eine prozedurale Gottheit — ein leuchtendes Auge mit Strahlenkranz.

### Wie Parotis reagieren

Die Reaktion hängt vom **Piety-Gen** (Frömmigkeit) und **Courage-Gen** (Mut) ab:

| Gen-Kombination | Reaktion |
|---|---|
| Piety hoch (>0.6) | Läuft zum Schrein, betet an, goldene Glyph-Blasen |
| Courage tief (<0.35) | Flieht vom Schrein |
| Courage hoch, Piety mittel | Neugierig, inspiziert den Schrein, blaue Blasen |

Der Schrein zeigt an wie viele Parotis gerade anbeten (🙏-Zähler).

---

## Das Postfach-System

### Wie es funktioniert

1. Du legst eine `.txt`-Datei in `~/parotis-inbox/`
2. Das Postfach-Icon (unten rechts) **glüht gelb** wenn Post da ist
3. Der **Postfach-Läufer** (Paroti mit höchster Klugheit + Mut, goldener Punkt) läuft automatisch zum Postfach
4. Er "öffnet" die Datei und führt alle Befehle aus
5. Die Datei wird nach `~/parotis-inbox/gelesen/` verschoben

### Befehle

Jeder Befehl steht auf einer eigenen Zeile. Zeilen mit `#` werden ignoriert.

| Befehl | Wirkung |
|---|---|
| `REGEN` | Starkregen — viel Futter erscheint überall |
| `FEST` | Grosses Fest — Massenfutter + alle Parotis glücklicher |
| `FRIEDEN` | Alle Parotis werden ruhiger und glücklicher |
| `NEU 5` | 5 neue Parotis werden erschaffen (max. 10 auf einmal) |
| `ALLE_WECKEN` | Alle schlafenden Parotis aufwecken |
| `NACHRICHT Hallo!` | Nachricht erscheint 12 Sekunden auf dem Bildschirm |
| `TIPP Tippe auf...` | Tipp-Hinweis anzeigen |
| `HILFE Text hier` | Hilfe-Text anzeigen |
| `BESTRAFT` | Gott ist zornig — 3 zufällige Parotis werden hungrig |
| `FEST` | Grosses Fest — Automaten befüllt, alle glücklich |

### Beispiel-Datei

```bash
# Neue Datei erstellen:
nano ~/parotis-inbox/befehl.txt
```

Inhalt:
```
# Mein erster Befehl
NACHRICHT Guten Morgen, kleine Wesen!
REGEN
NEU 2
```

Speichern → Der Postfach-Läufer holt es ab sobald er es bemerkt (alle 2 Sekunden geprüft).

---

## Touch-Steuerung & Menü

### Direkte Touch-Gesten

| Geste | Aktion |
|---|---|
| **Tippen** auf leere Fläche | Futter platzieren (3 Portionen) |
| **Tippen** auf einen Paroti | Streicheln → Glück + Vertrauen steigen |
| **Lang drücken** (>0.7 Sek.) | Regen — Futter erscheint überall |

### Touch-Menü

Grüner Kreis **unten links** → antippen zum Öffnen:

| Symbol | Funktion |
|---|---|
| 🌧 Regen | Futter überall |
| 🍎 Grosses Fest | Massenfutter + alle glücklich |
| ☮ Frieden | Alle Parotis beruhigen |
| 👶 Neues Leben | Einen neuen Paroti erschaffen |
| 📜 Chronik | Weltgeschichte ein-/ausblenden |
| ⚡ Alle wecken | Alle Schlafenden aufwecken |
| 🎵 Musik | Generative Musik ein/ausschalten |
| 🔌 Ausschalten | Welt speichern und beenden (Bestätigung) |

Das Menü ist für zukünftige Features erweiterbar (Fussball-Liga, etc.).

### Info-Panel

Einen Paroti antippen → **Info-Panel** erscheint rechts oben mit:
- Name, Generation, Alter
- Balken: Hunger, Energie, Glück, Vertrauen, Frömmigkeit
- Aktueller Zustand, Anzahl Kinder

---

## Das Genom erklärt

Jeder Paroti hat **15 Gene** die alles bestimmen:

### Visuelle Gene
| Gen | Effekt |
|---|---|
| `col_r / col_g / col_b` | Shirt-Farbe (RGB-Anteil 0–1) |
| `skin_tone` | Hautton (5 Varianten von hell bis dunkel) |
| `hair_dark` | Haarfarbe (hell bis dunkel) |
| `size` | Körpergrösse (26–40 Pixel) |

Sichtbare Accessoires je nach Gen-Wert:
- `intellect > 0.72` → Brille
- `piety > 0.72` → Heiligenschein
- Historiker → Stab
- Postfach-Läufer → Briefsymbol über dem Kopf

### Verhaltens-Gene
| Gen | Effekt |
|---|---|
| `speed` | Bewegungsgeschwindigkeit |
| `social` | Neigung zu anderen Parotis |
| `intellect` | Klugheit beim Futter-Suchen, Pfadfindung |
| `hunger_r` | Wie schnell Hunger steigt |
| `courage` | Mutig vs. ängstlich |
| `repro` | Fortpflanzungsdrang |
| `piety` | Frömmigkeit / Reaktion auf den Gott-Schrein |
| `tribe_r/g/b` | Stammes-Farbton — bestimmt Stammes-Zugehörigkeit |
| `sym_hunger/danger/love/joy` | Persönliche Symbole für jede Bedeutung (Index in Symbol-Pool) |
| `mut_rate` | Wie stark Kinder vom Elternteil abweichen |

### Abgeleitete Eigenschaften

- **Farbe**: direkt aus `col_r/g/b` → jede Linie hat eine charakteristische Farbe
- **Körpergrösse**: Paroti mit hohem `size`-Gen sind physisch grösser
- **Geschwindigkeit**: `speed`-Gen → schnelle Linien überleben besser wenn Futter rar
- **Hunger-Rate**: hoher `hunger_r` → stirbt schneller ohne Futter, braucht mehr Nahrung

---

## Paroti-Zustände

| Zustand | Beschreibung |
|---|---|
| **wandert** | Zufällige Erkundung der Welt |
| **sucht Futter** | Hunger > 42% — läuft gezielt zum nächsten Futter |
| **sucht Partner** | Fortpflanzungsbereit — sucht anderen willigen Paroti |
| **schläft** | Energie < 18% — ruht, träumt (lila Shimmer) |
| **sozialisiert** | Sucht Nähe zu anderen, Glyph-Blasen erscheinen |
| **betet an** | Läuft zum Gott-Schrein, goldene Blasen |
| **flieht (Gott!)** | Ängstliche fliehen vor dem Schrein |
| **neugierig** | Inspiziert den Schrein, blaue Blasen |
| **holt Post** | Postfach-Läufer — holt neue Befehle ab |
| **zum Automaten** | Hunger hoch → läuft zum Futter-Automaten |

---

## Evolutionsmechanik

### Fortpflanzung

1. Zwei Parotis im Zustand **sucht Partner** treffen sich
2. **Crossover**: Jedes Gen wird zufällig von Elter A oder B geerbt
3. **Mutation**: Gauss'sche Verschiebung ± `mut_rate` auf jeden Gen-Wert
4. Das Kind erscheint zwischen den Eltern
5. Generationszähler: `max(gen_A, gen_B) + 1`

### Natürliche Selektion

- Parotis mit hohem `hunger_r` verhungern schneller → werden seltener
- Parotis mit hohem `speed` + `intellect` finden Futter besser → überleben länger
- Parotis mit hohem `repro` + niedrigem `hunger_r` vermehren sich am häufigsten
- Nach vielen Generationen siehst du deutliche **Linien** mit gemeinsamen Merkmalen

### Sonderrollen

| Rolle | Vergabe | Markierung |
|---|---|---|
| **Historiker** | Ältester lebender Paroti | Kleiner Stab über dem Kopf |
| **Postfach-Läufer** | Höchste `intellect + courage` | Goldener Punkt über dem Kopf |

Rollen werden alle 5 Minuten neu vergeben.

---

## Persistenz & Speicherung

Die Welt überlebt Neustarts vollständig.

**Speicherort:** `~/.parotis/world.db` (SQLite)

**Gespeichert wird:**
- Alle lebenden Parotis (Gene, Zustand, Position, Abstammung, Piety, Frömmigkeit)
- Weltstatistiken (Tag, Max-Generation, Geburten, Tode)
- Weltchronik (wichtige Ereignisse der letzten 40 Einträge)

**Auto-Save:** alle 30 Sekunden während des Spiels

**Manueller Save:** beim Beenden über Menü (🔌 Ausschalten)

### Welt zurücksetzen

```bash
rm ~/.parotis/world.db
# Beim nächsten Start beginnt eine neue Welt mit 18 zufälligen Parotis
```

---

## Troubleshooting

### pygame nicht gefunden

```bash
sudo apt-get install python3-pygame
# oder:
pip3 install pygame --break-system-packages
```

### Touchscreen reagiert nicht

```bash
# SDL Touch-Backend prüfen:
export SDL_VIDEODRIVER=x11
python3 parotis.py

# Touch-Gerät prüfen:
ls /dev/input/event*
```

### Fullscreen auf falschem Display

```bash
export DISPLAY=:0
python3 parotis.py
```

### Cursor nicht versteckt

```bash
sudo apt-get install unclutter
# Dann start.sh verwenden statt parotis.py direkt
~/parotis/start.sh
```

### Postfach wird nicht verarbeitet

- Datei muss die Endung `.txt` haben
- Nur der Postfach-Läufer (goldener Punkt) holt die Post — er braucht etwas Zeit
- Prüfen ob `~/parotis-inbox/` existiert: `ls ~/parotis-inbox/`

### Gott-Bild wird nicht angezeigt

- Datei muss exakt `god.jpg`, `god.png`, `god.bmp` oder `god.webp` heissen
- Muss in `~/parotis-inbox/` liegen
- Spiel neu starten nach dem Hinzufügen

---

## Roadmap

### ✅ v2 (aktuell)
- [x] 15-Gen Genom-System (visuell + Verhalten + Piety)
- [x] 5 Körperformen × prozedurale Farbe/Grösse
- [x] Hunger, Energie, Glück, Vertrauen, Frömmigkeit
- [x] Fortpflanzung mit Crossover + Mutation
- [x] Gott-Schrein (eigenes Foto oder prozedurales Auge)
- [x] Paroti-Reaktionen auf Schrein (anbeten / fliehen / neugierig)
- [x] Postfach-System (`~/parotis-inbox/`)
- [x] Touch-Menü (kein Keyboard nötig)
- [x] Proto-Sprache: Glyph-Blasen bei Kommunikation
- [x] Traum-Visuals beim Schlafen
- [x] Historiker-Paroti & Postfach-Läufer
- [x] Desktop-Icon für Pi
- [x] SQLite-Persistenz (überlebt Neustarts)
- [x] Weltchronik

### ✅ v4 (aktuell) — Sprache, Stämme & Strukturen
- [x] **Emergente Sprache** — Parotis senden Symbole (◆★✦…) je nach Zustand (Hunger/Liebe/Gefahr/Freude), genetisch vererbt, konvergiert über Generationen. HUD zeigt dominante Symbole live.
- [x] **Stämme** — Parotis mit ähnlichen `tribe_r/g/b`-Genen bilden Stämme, Stammes-Farbe stark vererbt
- [x] **Territorien** — transparente Iso-Ellipsen mit Grenz-Dreiecken, alle 10 Sek neu berechnet
- [x] **Kollektives Gedächtnis** — `memory_trust` Dict (Stamm → Vertrauen), zu 85% an Kinder vererbt
- [x] **Nester** — Parotis mit hoher Energie bauen Zweig-Nester (isometrisch gezeichnet, verwittern)
- [x] **Mauern** — Stämme bauen Steinmauern an Territorium-Grenzen (iso, persistiert)
- [x] **Strukturen persistiert** — Nester + Mauern überleben Neustart (SQLite)
- [x] **Generative Musik** — BPM aus Speed, Tonhöhe aus Intellekt, Dur/Moll aus Stimmung, Lautstärke aus Populations-Grösse. Ein/ausschaltbar im Menü (🎵)
- [x] **Futter-Automaten** — 2 Automaten auf der Map, Parotis und Spieler können Futter holen
- [x] **Musik-Button** im Touch-Menü

### 🏟️ v4 – Fussball-Liga
Geplant sobald Populationen gross genug und territorial sind:
- Jede Spezies/Linie bekommt einen Fussballclub + Stadion
- Spielstärke basiert auf Genen (speed, intellect, courage, social)
- Wöchentliche Spiele (real 1× pro Woche, automatisch)
- Saisonrangliste persistent in SQLite
- Stadion wächst mit Club-Grösse

### 🔜 v5 – Die vierte Wand
- Parotis bemerken deinen Finger / deine Präsenz
- Systemnachricht nach vielen Generationen
- Historiker-Chronik als lesbare Weltgeschichte

---

## Datei-Struktur

```
~/parotis/
├── parotis.py          ← Hauptspiel
├── install.sh          ← Setup-Skript (einmalig ausführen)
├── start.sh            ← Empfohlener Start (Cursor versteckt, etc.)
├── Parotis.desktop     ← Desktop-Icon
├── icon.png            ← Programm-Icon (automatisch generiert)
├── generate_sprites.py ← Sprite-Generator (OpenAI API)
└── README.md           ← Diese Datei

~/parotis-inbox/        ← Postfach (Befehle per txt-Datei)
│   ├── BEFEHLE.txt.beispiel   ← Referenz aller Befehle
│   ├── god.jpg                ← Dein Foto (optional)
│   └── gelesen/               ← Ausgeführte Dateien landen hier

~/.parotis/
└── world.db            ← Spielstand (SQLite)
```

---

*Jede Welt ist einzigartig. Jede Generation ist ein Schritt ins Unbekannte.*  
*Was du erschaffst, entscheidet du — aber wie es sich entwickelt, entscheiden die Parotis.*
