#!/bin/bash
# ╔══════════════════════════════════════════════════╗
# ║  PAROTIS v2 – Raspberry Pi Setup               ║
# ╚══════════════════════════════════════════════════╝
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$HOME/Desktop"
INSTALL_DIR="$SCRIPT_DIR"   # Repo-Verzeichnis IST das Install-Verzeichnis

echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║      PAROTIS v2 – Setup & Installation        ║"
echo "╚════════════════════════════════════════════════╝"
echo ""
echo "▶ Installationsverzeichnis: $INSTALL_DIR"

# ── System-Pakete ─────────────────────────────────────────────────────────────
echo "▶ System-Pakete installieren ..."
sudo apt-get update -q
sudo apt-get install -y \
    python3-pip python3-pygame python3-numpy \
    libsdl2-dev libsdl2-ttf-dev libsdl2-image-dev \
    unclutter x11-xserver-utils

# ── Daten-Verzeichnis ─────────────────────────────────────────────────────────
mkdir -p "$HOME/.parotis"

# ── Postfach ──────────────────────────────────────────────────────────────────
echo "▶ Postfach anlegen: ~/parotis-inbox/"
mkdir -p "$HOME/parotis-inbox/gelesen"

# Willkommens-Nachricht nur wenn Postfach leer
if [ -z "$(ls -A "$HOME/parotis-inbox/"*.txt 2>/dev/null)" ]; then
    cat > "$HOME/parotis-inbox/willkommen.txt" << 'INBOX'
# Willkommen-Nachricht von Gott
# Dies ist dein erstes Postfach-Kommando.
# Der erste Paroti der es findet, wird es ausführen.

NACHRICHT Willkommen in der Welt der Parotis, ihr kleinen Wesen!
REGEN
INBOX
    echo "✅ Erste Nachricht ins Postfach gelegt."
fi

# Befehls-Referenz
cat > "$HOME/parotis-inbox/BEFEHLE.txt.beispiel" << 'HELP'
# ═══════════════════════════════════════════════════
#   PAROTIS POSTFACH – Verfügbare Befehle
#   (Diese Datei ist ein Beispiel – .beispiel = wird nicht ausgeführt)
# ═══════════════════════════════════════════════════
#
# Erstelle eine neue .txt Datei in ~/parotis-inbox/
# Der Postfach-Läufer holt sie ab und führt die Befehle aus.
# Danach wird die Datei nach ~/parotis-inbox/gelesen/ verschoben.
#
# REGEN                  → Starkregen (viel Futter)
# FEST                   → Grosses Fest (Futter + alle glücklich)
# FRIEDEN                → Alle Parotis werden glücklicher
# NEU 5                  → 5 neue Parotis erschaffen
# ALLE_WECKEN            → Alle schlafenden Parotis aufwecken
# NACHRICHT Hallo!       → Nachricht auf dem Bildschirm
# TIPP Tippe auf Futter  → Tipp-Hinweis anzeigen
# HILFE Text hier        → Hilfe-Hinweis anzeigen
# BESTRAFT               → 3 zufällige Parotis werden hungrig
#
# Mehrere Befehle pro Datei möglich (eine pro Zeile)
# Zeilen mit # werden ignoriert
# ═══════════════════════════════════════════════════
HELP

# ── Gott-Bild Hinweis ─────────────────────────────────────────────────────────
echo ""
echo "🙏 Gott-Bild (dein Foto):"
echo "   Lege dein Foto als eine der folgenden Dateien ab:"
echo "   ~/parotis-inbox/god.jpg"
echo "   ~/parotis-inbox/god.png"
echo "   (Das Bild wird auf 96×96px skaliert)"
echo ""

# ── Programm-Icon generieren ──────────────────────────────────────────────────
python3 -c "
import pygame
pygame.init()
s = pygame.Surface((64,64))
s.fill((12,28,14))
pygame.draw.circle(s,(80,200,100),(32,32),24)
pygame.draw.circle(s,(255,255,220),(32,32),10)
pygame.draw.circle(s,(30,20,0),(32,32),5)
pygame.image.save(s,'$INSTALL_DIR/icon.png')
print('✅ Icon generiert')
" 2>/dev/null || echo "⚠  Icon wird beim ersten Start generiert"

# ── Desktop-Icon ──────────────────────────────────────────────────────────────
mkdir -p "$DESKTOP_DIR"

# .desktop mit echtem Pfad und echtem User schreiben
cat > "$DESKTOP_DIR/Parotis.desktop" << DESKEOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Parotis
Comment=Die lebende Welt – Paroti Zivilisationssimulation
Exec=bash -c "cd $INSTALL_DIR && unclutter -idle 0.1 -root & xset s off & python3 parotis.py"
Icon=$INSTALL_DIR/icon.png
Terminal=false
Categories=Game;Simulation;
StartupNotify=false
DESKEOF

chmod +x "$DESKTOP_DIR/Parotis.desktop"

# Für LXDE (Pi OS Desktop): als vertrauenswürdig markieren
if command -v gio &>/dev/null; then
    gio set "$DESKTOP_DIR/Parotis.desktop" metadata::trusted true 2>/dev/null || true
fi

echo "✅ Desktop-Icon erstellt: $DESKTOP_DIR/Parotis.desktop"

# ── Start-Skript ──────────────────────────────────────────────────────────────
cat > "$INSTALL_DIR/start.sh" << STARTEOF
#!/bin/bash
cd "$INSTALL_DIR"
unclutter -idle 0.1 -root 2>/dev/null &
xset s off -dpms 2>/dev/null || true
python3 parotis.py
STARTEOF
chmod +x "$INSTALL_DIR/start.sh"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✅ Setup abgeschlossen!                                   ║"
echo "║                                                            ║"
echo "║  Start:    Doppelklick auf Desktop-Icon 'Parotis'         ║"
echo "║  Oder:     cd $INSTALL_DIR"
echo "║            ./start.sh                                      ║"
echo "║  Mit Maus: python3 parotis.py --mouse                     ║"
echo "║                                                            ║"
echo "║  Postfach: ~/parotis-inbox/  (txt-Dateien einlegen)      ║"
echo "║  Gott-Bild: ~/parotis-inbox/god.jpg                      ║"
echo "║  Daten:    ~/.parotis/world.db                           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
