#!/bin/bash

# Attachments Mailer Installation Script für Uberspace

set -e

echo "==================================="
echo "Attachments Mailer Uberspace Installation"
echo "==================================="

# Konfiguration
DOMAIN="rennecke.org"
SUBDIRECTORY=$(basename "$(pwd)")
INSTALL_PATH="$HOME/html/$SUBDIRECTORY"
SERVICE_NAME=$(basename "$(pwd)")

echo "Domain: $DOMAIN"
echo "Pfad: $INSTALL_PATH"
echo "Service: $SERVICE_NAME"
echo ""

# Funktion für Fehlerbehandlung
error_exit() {
    echo "FEHLER: $1" >&2
    exit 1
}

# Überprüfe ob wir auf Uberspace sind
if [[ ! -f "/etc/uberspace" ]] && [[ ! -d "/opt/uberspace" ]] && [[ $(hostname) != *"uberspace"* ]]; then
    echo "WARNUNG: Kann nicht eindeutig feststellen, ob dies ein Uberspace-Server ist."
    echo "Das Skript wird trotzdem fortgesetzt..."
    echo "Falls Sie nicht auf Uberspace sind, beenden Sie jetzt mit Ctrl+C"
    sleep 3
fi

echo "1. Erstelle notwendige Verzeichnisse..."
mkdir -p "$HOME/logs"
mkdir -p "$HOME/.config/services.d"

echo "2. Prüfe Installation..."
if [[ ! -d "$INSTALL_PATH" ]]; then
    error_exit "Installationsverzeichnis $INSTALL_PATH nicht gefunden! Bitte kopieren Sie zuerst alle Dateien dorthin."
fi

cd "$INSTALL_PATH"

if [[ ! -f "web_app.py" ]] || [[ ! -f "requirements.txt" ]]; then
    error_exit "Wichtige Dateien fehlen in $INSTALL_PATH. Bitte stellen Sie sicher, dass alle Projektdateien kopiert wurden."
fi

echo "3. Python Virtual Environment erstellen..."
python3 -m venv venv
source venv/bin/activate

echo "4. Abhängigkeiten installieren..."
pip install --upgrade pip
pip install -r requirements.txt

echo "5. Erstelle Uberspace Service (mit Auto-Fix)..."

# Cleanup any existing instances first
echo "Bereinige vorhandene Service-Instanzen..."
pkill -f "uvicorn.*web_app:app" 2>/dev/null || true
sleep 2
if pgrep -f "uvicorn.*web_app:app" > /dev/null; then
    echo "Force killing remaining processes..."
    pkill -9 -f "uvicorn.*web_app:app"
    sleep 1
fi

# Clean up old PID and service files
rm -f ~/logs/attachments-mailer.pid
rm -f "$HOME/.config/services.d/attachments-mailer.ini"
rm -f "$HOME/.config/services.d/$SERVICE_NAME.ini"

# Stop any supervisor services
supervisorctl stop attachments-mailer 2>/dev/null || true
supervisorctl stop "$SERVICE_NAME" 2>/dev/null || true

# Stelle sicher, dass das Services-Verzeichnis existiert
mkdir -p "$HOME/.config/services.d"
mkdir -p "$HOME/bin"

# Ermittle einen freien Port
echo "Ermittle freien Port..."
FREE_PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()")
echo "Verwende Port: $FREE_PORT"

# Create management scripts in ~/bin for background process approach
echo "Erstelle Service-Management-Skripte..."
cat > "$HOME/bin/start-attachments-mailer.sh" << EOF
#!/bin/bash
# Start-Skript für Attachments Mailer

# Erkenne verfügbare UTF-8 Locale
if locale -a | grep -q "en_US.utf8"; then
    export LC_ALL=en_US.utf8
    export LANG=en_US.utf8
    export LANGUAGE=en_US.utf8
elif locale -a | grep -q "en_US.UTF-8"; then
    export LC_ALL=en_US.UTF-8
    export LANG=en_US.UTF-8
    export LANGUAGE=en_US.UTF-8
elif locale -a | grep -q "de_DE.utf8"; then
    export LC_ALL=de_DE.utf8
    export LANG=de_DE.utf8
    export LANGUAGE=de_DE.utf8
elif locale -a | grep -q "C.utf8"; then
    export LC_ALL=C.utf8
    export LANG=C.utf8
    export LANGUAGE=C.utf8
else
    # Fallback: erste verfügbare UTF-8 Locale verwenden
    UTF8_LOCALE=\$(locale -a | grep -i utf8 | head -n 1)
    if [[ -n "\$UTF8_LOCALE" ]]; then
        export LC_ALL="\$UTF8_LOCALE"
        export LANG="\$UTF8_LOCALE"
        export LANGUAGE="\$UTF8_LOCALE"
        echo "Verwende Locale: \$UTF8_LOCALE"
    else
        echo "WARNUNG: Keine UTF-8 Locale gefunden. Versuche mit POSIX..."
        export LC_ALL=POSIX
        export LANG=POSIX
        export LANGUAGE=POSIX
    fi
fi

INSTALL_PATH="$INSTALL_PATH"
PORT="$FREE_PORT"
LOG_FILE="$HOME/logs/attachments-mailer.log"
PID_FILE="$HOME/logs/attachments-mailer.pid"

cd "\$INSTALL_PATH"

# Stoppe eventuell laufende Instanz
if [[ -f "\$PID_FILE" ]]; then
    OLD_PID=\$(cat "\$PID_FILE")
    if kill -0 "\$OLD_PID" 2>/dev/null; then
        echo "Stoppe laufende Instanz (PID: \$OLD_PID)"
        kill "\$OLD_PID"
        sleep 2
    fi
    rm -f "\$PID_FILE"
fi

# Aktiviere Virtual Environment
source venv/bin/activate

# Zeige verwendete Locale für Debugging
echo "Verwende Locale: \$LC_ALL"

# Starte uvicorn im Hintergrund mit korrekten Locale-Einstellungen
echo "Starte Attachments Mailer auf Port \$PORT..."
nohup uvicorn web_app:app --host 0.0.0.0 --port \$PORT > "\$LOG_FILE" 2>&1 &
echo \$! > "\$PID_FILE"

echo "Attachments Mailer gestartet (PID: \$!)"
echo "Logs: \$LOG_FILE"
echo "URL: https://$DOMAIN/$SUBDIRECTORY/"
EOF

cat > "$HOME/bin/stop-attachments-mailer.sh" << EOF
#!/bin/bash
# Stopp-Skript für Attachments Mailer

PID_FILE="$HOME/logs/attachments-mailer.pid"

if [[ -f "\$PID_FILE" ]]; then
    PID=\$(cat "\$PID_FILE")
    if kill -0 "\$PID" 2>/dev/null; then
        echo "Stoppe Attachments Mailer (PID: \$PID)"
        kill "\$PID"
        sleep 2
        if kill -0 "\$PID" 2>/dev/null; then
            echo "Force kill..."
            kill -9 "\$PID"
        fi
        rm -f "\$PID_FILE"
        echo "Attachments Mailer gestoppt"
    else
        echo "Process nicht gefunden (PID: \$PID)"
        rm -f "\$PID_FILE"
    fi
else
    echo "Keine PID-Datei gefunden"
fi
EOF

cat > "$HOME/bin/status-attachments-mailer.sh" << EOF
#!/bin/bash
# Status-Skript für Attachments Mailer

PID_FILE="$HOME/logs/attachments-mailer.pid"

if [[ -f "\$PID_FILE" ]]; then
    PID=\$(cat "\$PID_FILE")
    if kill -0 "\$PID" 2>/dev/null; then
        echo "✓ Attachments Mailer läuft (PID: \$PID)"
        echo "Port: $FREE_PORT"
        echo "URL: https://$DOMAIN/$SUBDIRECTORY/"
        echo "Logs: $HOME/logs/attachments-mailer.log"
        echo ""
        echo "Letzte Log-Einträge:"
        tail -n 10 "$HOME/logs/attachments-mailer.log" 2>/dev/null || echo "Keine Logs verfügbar"
    else
        echo "✗ Attachments Mailer läuft nicht (PID \$PID nicht gefunden)"
        rm -f "\$PID_FILE"
    fi
else
    echo "✗ Attachments Mailer läuft nicht (keine PID-Datei)"
fi
EOF

chmod +x "$HOME/bin/start-attachments-mailer.sh"
chmod +x "$HOME/bin/stop-attachments-mailer.sh"
chmod +x "$HOME/bin/status-attachments-mailer.sh"

echo "✓ Service-Management-Skripte erstellt"

echo "6. Service starten (Background Process Approach)..."

# Start the service using background process instead of supervisor
"$HOME/bin/start-attachments-mailer.sh"
sleep 5

# Get the actual PID and verify it's running
PID_FILE="$HOME/logs/attachments-mailer.pid"
if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "✓ Service erfolgreich gestartet (PID: $PID) auf Port $FREE_PORT"
        PORT=$FREE_PORT
    else
        echo "✗ Service konnte nicht gestartet werden"
        echo "Logs:"
        tail -n 20 "$HOME/logs/attachments-mailer.log" 2>/dev/null || echo "Log-Datei nicht verfügbar"
        exit 1
    fi
else
    echo "✗ PID-Datei nicht gefunden"
    exit 1
fi

echo "7. Web-Backend konfigurieren..."

# Configure Uberspace Web Backend (without --remove-prefix for better compatibility)
echo "Konfiguriere Uberspace Web Backend für /$SERVICE_NAME..."
uberspace web backend set "/$SERVICE_NAME" --http --port "$PORT"

if [ $? -eq 0 ]; then
    echo "✓ Web Backend erfolgreich konfiguriert"
else
    echo "✗ Fehler beim Konfigurieren des Web Backends"
    echo "Versuche manuell: uberspace web backend set /$SERVICE_NAME --http --port $PORT"
fi

# Apache .htaccess für zusätzliche Konfiguration (optional)
cat > ".htaccess" << EOF
# Zusätzliche Apache-Konfiguration für Attachments Mailer
RewriteEngine On

# CORS Headers für API
Header always set Access-Control-Allow-Origin "*"
Header always set Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS"
Header always set Access-Control-Allow-Headers "Content-Type, Authorization, X-Requested-With"

# Cache-Control für statische Dateien
<FilesMatch "\.(css|js|png|jpg|jpeg|gif|ico|svg)$">
    Header set Cache-Control "max-age=31536000, public"
</FilesMatch>
EOF

echo "✓ Web-Backend und .htaccess konfiguriert"

echo "8. Berechtigungen setzen..."
chmod -R 755 "$INSTALL_PATH"
chmod +x "$INSTALL_PATH/run_local.py"

echo "9. Erstelle Update-Skript..."
cat > "$INSTALL_PATH/update.sh" << 'EOF'
#!/bin/bash
# Update-Skript für Attachments Mailer

set -e

INSTALL_PATH=$(dirname "$0")

echo "Updating Attachments Mailer..."

cd "$INSTALL_PATH"

# Stoppe Service
~/bin/stop-attachments-mailer.sh

# Repository aktualisieren (falls git verfügbar)
if [[ -d ".git" ]]; then
    git pull
fi

# Virtual Environment aktivieren
source venv/bin/activate

# Abhängigkeiten aktualisieren
pip install --upgrade -r requirements.txt

# Service neustarten
~/bin/start-attachments-mailer.sh

echo "Update completed!"
EOF

chmod +x "$INSTALL_PATH/update.sh"

echo "10. Teste Installation mit integrierter Diagnose..."
sleep 3

# Test ob der Service läuft
echo "Teste Backend auf Port $PORT..."
if curl -s "http://127.0.0.1:$PORT/" > /dev/null; then
    echo "✓ Backend läuft korrekt auf Port $PORT"
    ACTUAL_PORT=$PORT
else
    echo "✗ Backend antwortet nicht auf Port $PORT"
    echo "Service Status:"
    "$HOME/bin/status-attachments-mailer.sh"
    echo "Logs:"
    tail -n 20 "$HOME/logs/attachments-mailer.log"
    exit 1
fi

echo "Teste externe Erreichbarkeit..."
sleep 2
if curl -s "https://$DOMAIN/$SERVICE_NAME/" > /dev/null; then
    echo "✓ Anwendung ist extern erreichbar"
else
    echo "⚠ Anwendung noch nicht extern erreichbar"
    echo "Dies kann einige Minuten dauern, bis die Konfiguration aktiv wird."
    echo ""
    echo "Diagnostiziere Web Backend Konfiguration..."
    echo "Aktuelle Web Backend Konfiguration:"
    uberspace web backend list | grep "/$SERVICE_NAME" || echo "Kein /$SERVICE_NAME Backend gefunden"
fi

# Test API endpoints
echo ""
echo "Teste API-Endpunkte..."
echo "Health Check:"
curl -s "http://127.0.0.1:$PORT/health" 2>/dev/null | head -c 100 || echo "Health endpoint nicht verfügbar"

echo ""
echo "Debug endpoint:"
curl -s "http://127.0.0.1:$PORT/debug" 2>/dev/null | head -c 100 || echo "Debug endpoint nicht verfügbar"

echo ""
echo "11. Finaler Restart für optimale Konfiguration..."

# Stop current service
echo "Stoppe Service für finalen Restart..."
"$HOME/bin/stop-attachments-mailer.sh"
sleep 2

# Update web backend configuration to ensure it's correct
echo "Aktualisiere Web Backend Konfiguration..."
uberspace web backend set "/$SERVICE_NAME" --http --port "$PORT" --remove-prefix

# Start service again
echo "Starte Service neu..."
"$HOME/bin/start-attachments-mailer.sh"
sleep 3

echo ""
echo "Prüfe finale Service-Konfiguration..."
"$HOME/bin/status-attachments-mailer.sh"

echo ""
echo "Prüfe Web Backend Status..."
uberspace web backend list | grep "/$SERVICE_NAME"

echo ""
echo "Teste finale Verbindungen..."
echo "Interne Verbindung:"
if curl -s "http://127.0.0.1:$PORT/" > /dev/null; then
    echo "✓ Interne Verbindung funktioniert"
else
    echo "✗ Interne Verbindung fehlgeschlagen"
fi

echo ""
echo "Externe Verbindung:"
if curl -s "https://rennecke.org/$SERVICE_NAME/" > /dev/null; then
    echo "✓ Externe Verbindung funktioniert"
else
    echo "✗ Externe Verbindung fehlgeschlagen"
fi

echo ""
echo "API Endpunkt Test:"
if curl -s -X GET "https://rennecke.org/$SERVICE_NAME/upload-csv" > /dev/null; then
    echo "✓ API Endpunkt erreichbar"
else
    echo "✗ API Endpunkt nicht erreichbar"
fi

echo ""
echo "==================================="
echo "✓ Installation erfolgreich!"
echo "==================================="
echo ""
echo "Die Attachments Mailer Anwendung ist jetzt verfügbar unter:"
echo "https://$DOMAIN/$SUBDIRECTORY/"
echo ""
echo "Service Information:"
echo "- Interner Port: $PORT"
echo "- Web Backend: /$SERVICE_NAME -> Port $PORT (mit --remove-prefix)"
echo "- Status: Läuft als Background-Prozess"
echo ""
echo "Nützliche Befehle:"
echo "- Service status: ~/bin/status-attachments-mailer.sh"
echo "- Service starten: ~/bin/start-attachments-mailer.sh"
echo "- Service stoppen: ~/bin/stop-attachments-mailer.sh"
echo "- Logs anzeigen: tail -f ~/logs/attachments-mailer.log"
echo "- Update: cd $INSTALL_PATH && ./update.sh"
echo "- Web Backend prüfen: uberspace web backend list"
echo ""
echo "Verzeichnisse:"
echo "- Installation: $INSTALL_PATH"
echo "- Logs: ~/logs/attachments-mailer.log"
echo "- Scripts: ~/bin/*attachments-mailer*"
echo ""
echo "WICHTIG:"
echo "1. Bei Problemen prüfen Sie die Logs: tail -f ~/logs/attachments-mailer.log"
echo "2. Web Backend Status: uberspace web backend list"
echo "3. Falls extern nicht erreichbar: uberspace web backend set /$SERVICE_NAME --http --port $PORT --remove-prefix"
echo "4. Die Anwendung speichert Email-Konfigurationen im Browser (localStorage)"
echo "5. Passwörter werden NICHT gespeichert und müssen bei jeder Sitzung neu eingegeben werden"
echo "6. Attachments werden in das 'attachments/' Verzeichnis hochgeladen"
echo "7. Der Service läuft als einfacher Background-Prozess (nicht über supervisor)"
echo "8. Nach dem finalen Restart sollten alle Upload-Funktionen korrekt arbeiten"
echo ""

# Zeige aktuellen Status
"$HOME/bin/status-attachments-mailer.sh"
