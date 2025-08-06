# Attachments Mailer - Web Application

Eine Webanwendung für den E-Mail-Versand mit personalisierten Anhängen.

Wenn du nur ein simples Python-Script suchst, das das erledigt:
[simple-mailer](https://github.com/paulrennecke/simple-mailer)

###  [Live Demo](https://paul-rennecke.de/mailer)


## Features

- **Web-Interface**: Benutzerfreundliche Oberfläche für E-Mail-Konfiguration und -Versand
- **localStorage**: E-Mail-Konfigurationen werden lokal gespeichert (außer Passwörtern)
- **CSV/Excel-Upload**: Bulk-E-Mail-Versand basierend auf CSV- oder Excel-Dateien (XLS/XLSX)
- **Anhang-Management**: Upload und Verwaltung von PDF-Anhängen
- **Vorschau**: Überprüfung aller E-Mails vor dem Versand
- **Bild-Integration**: Einbindung von Bildern als Inline-Inhalte
- **Session-Management**: Temporäre Dateiverwaltung mit automatischer Bereinigung
- **Platzhalter-System**: Dynamische Personalisierung mit benutzerdefinierten Platzhaltern
- **Live-Vorschau**: Echtzeitvorschau des HTML-E-Mail-Inhalts
- **Flexible Datenstruktur**: Anpassbare Spalten-Zuordnung für verschiedene CSV-Formate
- **Validierung**: Automatische Überprüfung von E-Mail-Adressen und Anhängen

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
- **SMTP-Server**: Server, Port und Authentifizierung konfigurieren
- **E-Mail-Adresse**: Absender-E-Mail und Passwort eingeben
- **Betreff**: E-Mail-Betreff definieren
- Konfiguration wird im localStorage gespeichert (außer Passwort)

### 2. E-Mail erstellen
- **HTML-Editor**: Integrierter Editor mit Live-Vorschau
- **Platzhalter**: Dynamische Inhalte mit `{{platzhalter}}` Syntax
- **Bilder**: Upload und Einbindung von Bildern als Inline-Inhalte
- **Formatierung**: Automatische HTML-Formatierung verfügbar
- **Templates**: Beispiel-Templates als Startpunkt

### 3. Dateien hochladen
- **CSV/Excel-Datei**: Liste mit E-Mail-Adressen und Daten (CSV, XLS, XLSX)
- **Spalten-Zuordnung**: Flexible Zuordnung von Spalten zu E-Mail, Anhang und Platzhaltern
- **Datenvalidierung**: Automatische Überprüfung der E-Mail-Adressen
- **Editierbare Tabelle**: Manuelle Bearbeitung der Daten vor dem Versand
- **Anhänge**: PDF-Dateien für den personalisierten Versand

### 4. Vorschau & Validierung
- **E-Mail-Vorschau**: Überprüfung aller E-Mails und Platzhalter
- **Anhang-Prüfung**: Anzeige von fehlenden oder verfügbaren Anhängen
- **Status-Anzeige**: Farbkodierte Darstellung des Validierungsstatus
- **Fehler-Report**: Detaillierte Auflistung von Problemen

### 5. Versand
- **Bulk-Versand**: Automatischer Versand an alle gültigen E-Mail-Adressen
- **Fortschrittsanzeige**: Live-Verfolgung des Versandfortschritts
- **Ergebnis-Report**: Detaillierte Auflistung erfolgreicher und fehlgeschlagener Sendungen
- **Abbruch-Funktion**: Möglichkeit zum Stoppen des laufenden Versands

## CSV/Excel-Format

Die Datendatei kann in verschiedenen Formaten hochgeladen werden:

### Unterstützte Formate
- **CSV**: Kommagetrennte Werte (.csv)
- **Excel**: Moderne Excel-Dateien (.xlsx)
- **Excel Legacy**: Ältere Excel-Dateien (.xls)

### Beispiel-Struktur
```csv
emails,attachments,name,firma
user1@example.com,ABC123,Max Mustermann,Firma A
user2@example.com,DEF456,Anna Schmidt,Firma B
```

### Spalten-Zuordnung
- **E-Mail-Spalte**: Enthält die Empfänger-E-Mail-Adressen
- **Anhang-Spalte**: Dateiname der personalisierten Anhänge (ohne .pdf-Endung)
- **Platzhalter-Spalten**: Beliebige weitere Spalten für dynamische Inhalte

### Platzhalter-System
- Verwenden Sie `{{spaltenname}}` in Ihrem HTML-E-Mail-Template
- Beispiel: `Sehr geehrte/r {{name}}, vielen Dank für Ihr Interesse an {{firma}}.`
- Platzhalter werden automatisch durch die entsprechenden Spaltenwerte ersetzt

## Technische Details

### Backend (FastAPI)
- **Framework**: FastAPI
- **ASGI Server**: Uvicorn (mit Hot-Reload für Entwicklung)
- **Template Engine**: Jinja2
- **File Handling**: python-multipart, aiofiles
- **Data Processing**: pandas (CSV/Excel-Verarbeitung)
- **Email**: smtplib (SMTP-Verbindungen mit SSL/TLS)
- **Session Management**: UUID-basierte Session-IDs mit temporären Verzeichnissen

### Frontend
- **Framework**: Bootstrap 5
- **Icons**: Font Awesome 6
- **JavaScript**: Vanilla JS (ES6+)
- **Storage**: Browser localStorage für Konfiguration
- **Upload**: Drag & Drop Unterstützung
- **Editor**: Integrierter HTML-Editor mit Live-Vorschau

### Datenverwaltung
- **Session-basiert**: Temporäre Dateien pro Benutzer-Session
- **Auto-Cleanup**: Automatische Bereinigung nach 24 Stunden
- **Validierung**: Client- und serverseitige Validierung
- **Sicherheit**: Keine Persistierung sensibler Daten

### Deployment
- **Platform**: Uberspace
- **Process Manager**: Supervisor
- **Web Server**: Apache (Reverse Proxy)
- **SSL**: Automatisch via Uberspace

## Verzeichnisstruktur

```
online-mailer/
├── web_app.py              # FastAPI Hauptanwendung (697 Zeilen)
├── run_local.py            # Lokaler Entwicklungsserver
├── install_uberspace.sh    # Uberspace Installationsskript (443 Zeilen)
├── requirements.txt        # Python Dependencies (10 Pakete)
├── templates/
│   └── index.html         # Haupt-Web-Interface (Single Page App)
├── static/
│   ├── icon.ico           # Favicon
│   └── icon.png           # App Icon
```

### Datei-Details
- **web_app.py**: Hauptanwendung mit allen API-Endpunkten, Session-Management und E-Mail-Versand
- **index.html**: Vollständige Single-Page-Anwendung mit integriertem JavaScript
- **install_uberspace.sh**: Vollautomatisches Deployment-Skript für Uberspace-Hosting
- **requirements.txt**: Minimale Dependencies (FastAPI, Uvicorn, Pandas, etc.)

## Sicherheitshinweise

- **Passwort-Sicherheit**: Passwörter werden NIEMALS im localStorage oder auf dem Server gespeichert
- **Session-Sicherheit**: Automatische Bereinigung temporärer Dateien nach 24 Stunden
- **Upload-Validierung**: Strenge Beschränkung auf erlaubte Dateitypen (PDF, PNG, JPG, HTML, CSV, XLS, XLSX)
- **SMTP-Verschlüsselung**: Alle SMTP-Verbindungen nutzen SSL/TLS-Verschlüsselung
- **Datenschutz**: Keine dauerhafte Persistierung von E-Mail-Adressen oder persönlichen Daten
- **Session-Isolation**: Jeder Benutzer erhält eine isolierte Session mit eigenen temporären Dateien

## API-Endpunkte

Die Anwendung stellt folgende REST-API-Endpunkte zur Verfügung:

### Konfiguration & Test
- `POST /test-config` - SMTP-Konfiguration testen
- `GET /session-files/{session_id}/{filename}` - Session-Dateien abrufen

### Datenverarbeitung
- `POST /upload-data-file` - CSV/Excel-Dateien hochladen
- `POST /select-columns` - Spalten-Zuordnung verarbeiten
- `POST /update-table-data` - Tabellendaten aktualisieren

### Dateiverwaltung
- `POST /upload-attachments` - PDF-Anhänge hochladen
- `POST /upload-images` - Bilder hochladen
- `POST /upload-email-body` - E-Mail-HTML-Inhalt speichern
- `GET /list-attachments` - Anhänge auflisten
- `DELETE /remove-attachment` - Einzelnen Anhang entfernen
- `DELETE /remove-all-attachments` - Alle Anhänge entfernen

### E-Mail-Versand
- `POST /preview-emails` - E-Mail-Vorschau generieren
- `POST /send-emails` - Bulk-E-Mail-Versand durchführen

## Deployment-Details

### Lokale Entwicklung
```bash
# Virtuelle Umgebung erstellen (empfohlen)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate     # Windows

# Dependencies installieren
pip install -r requirements.txt

# Entwicklungsserver starten (mit Hot-Reload)
python run_local.py
```

### Produktions-Deployment (Uberspace)
Das `install_uberspace.sh` Skript führt folgende Schritte aus:
1. Erstellt Supervisor-Konfiguration für Prozess-Management
2. Konfiguriert Apache-Reverse-Proxy (.htaccess)
3. Installiert Python-Dependencies in virtueller Umgebung
4. Startet den Service automatisch
5. Richtet Logging ein

```bash
# Automatische Installation
chmod +x install_uberspace.sh
./install_uberspace.sh
```

```bash
# Service Status prüfen
supervisorctl status attachments-mailer

# Service neustarten
supervisorctl restart attachments-mailer

# Logs anzeigen
tail -f ~/logs/attachments-mailer.log

# Update durchführen
cd ~/html/online-mailer && git pull origin main && supervisorctl restart attachments-mailer
```

## Note
This project was created as part of "Vibe coding". Please keep this in mind.