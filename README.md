# Attachments Mailer - Web Application

Eine FastAPI-basierte Webanwendung für den E-Mail-Versand mit personalisierten Anhängen.

## Features

- **Web-Interface**: Benutzerfreundliche Oberfläche für E-Mail-Konfiguration und -Versand
- **localStorage**: E-Mail-Konfigurationen werden lokal gespeichert (außer Passwörtern)
- **CSV-Upload**: Bulk-E-Mail-Versand basierend auf CSV-Daten
- **Anhang-Management**: Upload und Verwaltung von PDF-Anhängen
- **Vorschau**: Überprüfung aller E-Mails vor dem Versand
- **Logo-Integration**: Einbindung von Logos als Inline-Bilder

## Installation

### Lokale Entwicklung

1. Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

2. Anwendung starten:
```bash
python run_local.py
```

3. Browser öffnen: `http://localhost:8000`

### Uberspace Deployment

1. Repository auf Uberspace klonen
2. Installationsskript ausführen:
```bash
chmod +x install_uberspace.sh
./install_uberspace.sh
```

## Nutzung

### 1. Konfiguration
- E-Mail-Adresse, SMTP-Server, Port und Betreff eingeben
- Konfiguration wird im localStorage gespeichert (außer Passwort)

### 2. Dateien hochladen
- **CSV-Datei**: Liste mit E-Mail-Adressen und Anhang-Referenzen
- **E-Mail-Body**: HTML-Datei mit dem E-Mail-Inhalt
- **Logo**: PNG-Datei für Inline-Darstellung (optional)
- **Anhänge**: PDF-Dateien für den Versand

### 3. Vorschau
- Überprüfung aller E-Mails und Anhänge
- Anzeige von Problemen (fehlende Anhänge, etc.)

### 4. Versand
- Bulk-Versand an alle gültigen E-Mail-Adressen
- Fortschrittsanzeige und Ergebnis-Report

## CSV-Format

Die CSV-Datei muss folgende Spalten enthalten:

```csv
emails,attachments
user1@example.com,ABC123
user2@example.com,DEF456
```

- `emails`: E-Mail-Adressen der Empfänger
- `attachments`: Dateiname der Anhänge (ohne .pdf-Endung)

## Technische Details

### Backend (FastAPI)
- **Framework**: FastAPI
- **ASGI Server**: Uvicorn
- **Template Engine**: Jinja2
- **File Handling**: python-multipart, aiofiles

### Frontend
- **Framework**: Bootstrap 5
- **Icons**: Font Awesome
- **JavaScript**: Vanilla JS (ES6+)
- **Storage**: Browser localStorage

### Deployment
- **Platform**: Uberspace
- **Process Manager**: Supervisor
- **Web Server**: Apache (Reverse Proxy)
- **SSL**: Automatisch via Uberspace

## Verzeichnisstruktur

```
attachments-mailer/
├── web_app.py              # FastAPI Hauptanwendung
├── run_local.py            # Lokaler Entwicklungsserver
├── install_uberspace.sh    # Uberspace Installationsskript
├── configure_uberspace.sh  # Uberspace Konfigurationsskript
├── requirements_web.txt    # Python Dependencies
├── templates/
│   └── index.html         # Haupt-Web-Interface
├── static/
│   └── style.css          # Zusätzliche Styles
├── attachments/           # Upload-Verzeichnis für PDFs
├── email_body.html        # E-Mail-Inhalt (wird hochgeladen)
├── ticketree.png         # Logo (wird hochgeladen)
└── .env                  # Umgebungsvariablen (wird generiert)
```

## Sicherheitshinweise

- Passwörter werden NICHT im localStorage gespeichert
- Alle Uploads sind auf erlaubte Dateitypen beschränkt
- SMTP-Verbindungen nutzen SSL/TLS
- Keine Persistierung von sensiblen Daten auf dem Server

## Uberspace-spezifische Befehle

```bash
# Service Status prüfen
supervisorctl status attachments-mailer

# Service neustarten
supervisorctl restart attachments-mailer

# Logs anzeigen
tail -f ~/logs/attachments-mailer.log

# Update durchführen
cd ~/html/send-mail && ./update.sh
```

## Support

Bei Problemen prüfen Sie:

1. Service-Status: `supervisorctl status attachments-mailer`
2. Logs: `tail -f ~/logs/attachments-mailer.log`
3. Port-Konfiguration in `.htaccess`
4. Apache-Konfiguration für mod_proxy

## Lizenz

Dieses Projekt ist für den privaten und kommerziellen Gebrauch freigegeben.
