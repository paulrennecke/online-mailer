from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import smtplib
import pandas as pd
import os
import io
import time
import tempfile
import shutil
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
import traceback
import logging
from typing import List, Dict
import json
from pydantic import BaseModel

app = FastAPI(title="Simple Mailer", description="Email Versand Tool")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve session files
@app.get("/session-files/{session_id}/{filename}")
async def get_session_file(session_id: str, filename: str):
    """Serve files from user's session"""
    if session_id not in user_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = user_sessions[session_id]
    
    # Check if file exists in session's images or attachments
    file_path = None
    
    if filename in session.get("images", {}):
        file_path = session["images"][filename]["path"]
    elif filename in session.get("attachments", {}):
        file_path = session["attachments"][filename]["path"]
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(file_path)

# Templates
templates = Jinja2Templates(directory="templates")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Session storage for temporary files
user_sessions: Dict[str, Dict] = {}

def get_session_id(request: Request) -> str:
    """Get or create session ID for user"""
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        session_id = str(uuid.uuid4())
    
    if session_id not in user_sessions:
        user_sessions[session_id] = {
            "temp_dir": tempfile.mkdtemp(),
            "images": {},
            "attachments": {},
            "created_at": time.time()
        }
    
    return session_id

def cleanup_old_sessions():
    """Clean up sessions older than 24 hours"""
    current_time = time.time()
    expired_sessions = []
    
    for session_id, session_data in user_sessions.items():
        if current_time - session_data["created_at"] > 86400:  # 24 hours
            expired_sessions.append(session_id)
    
    for session_id in expired_sessions:
        session_data = user_sessions[session_id]
        if os.path.exists(session_data["temp_dir"]):
            shutil.rmtree(session_data["temp_dir"])
        del user_sessions[session_id]

class EmailConfig(BaseModel):
    email_login: str
    email_password: str
    smtp_server: str
    smtp_port: int
    email_subject: str

class EmailData(BaseModel):
    emails: List[str]
    attachments: List[str]

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    cleanup_old_sessions()  # Clean up old sessions on page load
    session_id = get_session_id(request)
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "session_id": session_id
    })

@app.post("/test-config")
async def test_config(config: dict):
    try:
        # Extract configuration
        email_login = config.get('email_login')
        email_password = config.get('email_password')
        smtp_server = config.get('smtp_server')
        smtp_port = int(config.get('smtp_port', 465))
        
        # Validate required fields
        if not all([email_login, email_password, smtp_server]):
            raise HTTPException(status_code=400, detail="Alle Konfigurationsdaten sind erforderlich")
        
        # Test SMTP connection
        try:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            server.login(email_login, email_password)
            server.quit()
            
            return {"success": True, "message": "SMTP-Konfiguration erfolgreich getestet"}
            
        except smtplib.SMTPAuthenticationError:
            raise HTTPException(status_code=400, detail="SMTP-Authentifizierung fehlgeschlagen. Überprüfen Sie Email und Passwort.")
        except smtplib.SMTPConnectError:
            raise HTTPException(status_code=400, detail="Verbindung zum SMTP-Server fehlgeschlagen. Überprüfen Sie Server und Port.")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"SMTP-Verbindung fehlgeschlagen: {str(e)}")
            
    except Exception as e:
        logging.error(f"Config test error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fehler beim Testen der Konfiguration: {str(e)}")

@app.post("/upload-csv")
async def upload_csv(request: Request, file: UploadFile = File(...)):
    try:
        session_id = get_session_id(request)
        session = user_sessions[session_id]
        
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        
        # Validate CSV structure
        if 'emails' not in df.columns or 'attachments' not in df.columns:
            raise HTTPException(status_code=400, detail="CSV muss 'emails' und 'attachments' Spalten enthalten")
        
        # Convert to list of dictionaries
        data = df.to_dict('records')
        
        # Store CSV data in session
        session["csv_data"] = data
        
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Lesen der CSV: {str(e)}")

@app.post("/upload-attachments")
async def upload_attachments(request: Request, files: List[UploadFile] = File(...)):
    """Upload attachments for current session"""
    try:
        session_id = get_session_id(request)
        session = user_sessions[session_id]
        
        uploaded_files = []
        for file in files:
            if file.filename and file.filename != '':
                # Create unique filename
                file_extension = os.path.splitext(file.filename)[1]
                unique_filename = f"{str(uuid.uuid4())}{file_extension}"
                
                # Save to session's temp directory
                file_path = os.path.join(session["temp_dir"], unique_filename)
                
                with open(file_path, "wb") as f:
                    content = await file.read()
                    f.write(content)
                
                # Store in session
                session["attachments"][unique_filename] = {
                    "original_name": file.filename,
                    "path": file_path,
                    "size": len(content)
                }
                
                uploaded_files.append({
                    "filename": unique_filename,
                    "original_name": file.filename
                })
        
        return {"success": True, "uploaded_files": uploaded_files}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Hochladen der Anhänge: {str(e)}")

@app.post("/upload-email-body")
async def upload_email_body(request: Request):
    try:
        session_id = get_session_id(request)
        session = user_sessions[session_id]
        
        # Check if it's JSON content (from editor) or file upload
        content_type = request.headers.get('content-type', '')
        
        if 'application/json' in content_type:
            # Handle JSON content from editor
            data = await request.json()
            email_body = data.get('content', '')
        else:
            # Handle file upload
            form = await request.form()
            file = form.get('file')
            if not file:
                raise HTTPException(status_code=400, detail="Keine Datei bereitgestellt")
            
            contents = await file.read()
            email_body = contents.decode('utf-8')
        
        # Save to session's temp directory
        email_body_path = os.path.join(session["temp_dir"], 'email_body.html')
        with open(email_body_path, 'w', encoding='utf-8') as f:
            f.write(email_body)
        
        session["email_body"] = {
            "path": email_body_path,
            "content": email_body
        }
        
        return {"success": True, "body": email_body}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Verarbeiten des Email-Body: {str(e)}")

@app.post("/upload-images")
async def upload_images(request: Request, files: List[UploadFile] = File(...)):
    """Upload images for current session"""
    try:
        session_id = get_session_id(request)
        session = user_sessions[session_id]
        
        uploaded_files = []
        
        for file in files:
            if file.filename and file.filename != '':
                # Create unique filename
                file_extension = os.path.splitext(file.filename)[1]
                unique_filename = f"{str(uuid.uuid4())}{file_extension}"
                
                # Save to session's temp directory
                file_path = os.path.join(session["temp_dir"], unique_filename)
                
                with open(file_path, "wb") as buffer:
                    content = await file.read()
                    buffer.write(content)
                
                # Store in session
                session["images"][unique_filename] = {
                    "original_name": file.filename,
                    "path": file_path,
                    "size": len(content)
                }
                
                uploaded_files.append(unique_filename)
        
        return {"success": True, "uploaded_files": uploaded_files}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Hochladen der Bilder: {str(e)}")

@app.post("/preview-emails")
async def preview_emails(request: Request, email_data: dict):
    try:
        session_id = get_session_id(request)
        session = user_sessions[session_id]
        
        csv_data = email_data.get('csv_data', [])
        
        if not csv_data:
            raise HTTPException(status_code=400, detail="Keine CSV-Daten vorhanden")
        
        valid_emails = []
        invalid_emails = []
        
        for row in csv_data:
            email = row['emails']
            attachment_filename = row['attachments']
            
            # Find attachment in session using same logic as send_emails
            attachment_found = False
            found_attachment_name = None
            
            for filename, file_data in session.get("attachments", {}).items():
                original_name = file_data["original_name"]
                
                # Use same matching strategies as in send_emails
                if (original_name == attachment_filename or
                    os.path.splitext(original_name)[0] == os.path.splitext(attachment_filename)[0] or
                    attachment_filename + '.pdf' == original_name or
                    os.path.splitext(original_name)[0] == attachment_filename):
                    
                    attachment_found = True
                    found_attachment_name = original_name
                    break
            
            if attachment_found:
                valid_emails.append({
                    'email': email,
                    'attachment': found_attachment_name,
                    'status': 'valid'
                })
            else:
                invalid_emails.append({
                    'email': email,
                    'attachment': attachment_filename,
                    'status': 'missing_attachment'
                })
        
        return {
            "valid_emails": valid_emails,
            "invalid_emails": invalid_emails,
            "total_valid": len(valid_emails),
            "total_invalid": len(invalid_emails)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler bei der Vorschau: {str(e)}")

@app.post("/send-emails")
async def send_emails(request: Request, request_data: dict):
    try:
        session_id = get_session_id(request)
        session = user_sessions[session_id]
        
        config = request_data.get('config')
        csv_data = request_data.get('csv_data', [])
        
        if not config or not csv_data:
            raise HTTPException(status_code=400, detail="Konfiguration oder CSV-Daten fehlen")
        
        # Email account configuration
        login_acc = config.get('email_login')
        login_pass = config.get('email_password')
        smtp_server = config.get('smtp_server')
        smtp_port = int(config.get('smtp_port', 465))
        email_subject = config.get('email_subject')
        
        # Validate configuration
        if not all([login_acc, login_pass, smtp_server, email_subject]):
            raise HTTPException(status_code=400, detail="Alle Email-Konfigurationsdaten sind erforderlich")
        
        # Read email body from session
        email_body_path = os.path.join(session["temp_dir"], 'email_body.html')
        if not os.path.exists(email_body_path):
            # Fallback to default location
            if os.path.exists('email_body.html'):
                with open('email_body.html', 'r', encoding='utf-8') as f:
                    email_body = f.read()
            else:
                raise HTTPException(status_code=400, detail="Email-Body nicht gefunden")
        else:
            with open(email_body_path, 'r', encoding='utf-8') as f:
                email_body = f.read()
        
        # Connect to SMTP server
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(login_acc, login_pass)
        
        sent_emails = []
        failed_emails = []
        
        for row in csv_data:
            try:
                email = row['emails']
                attachment_filename = row['attachments']
                
                # Find attachment in session - try multiple matching strategies
                attachment_path = None
                attachment_original_name = None
                
                for filename, file_data in session.get("attachments", {}).items():
                    original_name = file_data["original_name"]
                    
                    # Strategy 1: Exact match with original name
                    if original_name == attachment_filename:
                        attachment_path = file_data["path"]
                        attachment_original_name = original_name
                        break
                    
                    # Strategy 2: Match with filename (no extension) from CSV
                    original_name_no_ext = os.path.splitext(original_name)[0]
                    attachment_no_ext = os.path.splitext(attachment_filename)[0]
                    if original_name_no_ext == attachment_no_ext:
                        attachment_path = file_data["path"]
                        attachment_original_name = original_name
                        break
                    
                    # Strategy 3: Check if CSV entry matches filename with .pdf extension
                    if attachment_filename + '.pdf' == original_name:
                        attachment_path = file_data["path"]
                        attachment_original_name = original_name
                        break
                    
                    # Strategy 4: Check if original name without extension matches CSV entry
                    if original_name_no_ext == attachment_filename:
                        attachment_path = file_data["path"]
                        attachment_original_name = original_name
                        break
                
                # Skip if attachment doesn't exist
                if not attachment_path or not os.path.exists(attachment_path):
                    failed_emails.append({
                        'email': email,
                        'error': f'Anhang "{attachment_filename}" nicht gefunden'
                    })
                    continue
                
                # Create a new message for each email
                msg = MIMEMultipart()
                msg['From'] = login_acc
                msg['To'] = email
                msg['Subject'] = email_subject
                
                # Process email body to replace image references and attach images
                processed_email_body = email_body
                
                # Add all session images as inline attachments and update HTML references
                for filename, file_data in session.get("images", {}).items():
                    try:
                        original_name = file_data["original_name"]
                        file_path = file_data["path"]
                        
                        # Generate CID based on filename (consistent with frontend)
                        filename_base = os.path.splitext(original_name)[0]
                        image_cid = f"img-{filename_base}"
                        
                        # Check if this image is referenced in the email body
                        if f"cid:{image_cid}" in processed_email_body:
                            # Add image as inline attachment
                            with open(file_path, 'rb') as img:
                                image = MIMEImage(img.read())
                                image.add_header('Content-ID', f'<{image_cid}>')
                                image.add_header('Content-Disposition', 'inline', filename=original_name)
                                msg.attach(image)
                                
                    except Exception as img_err:
                        logging.error(f"Failed to attach image {filename}: {str(img_err)}")
                
                # Attach the processed email body
                msg.attach(MIMEText(processed_email_body, 'html'))
                
                # Create the attachment for this specific email
                with open(attachment_path, 'rb') as attachment_file:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment_file.read())
                    encoders.encode_base64(part)
                    # Use the original filename that was found
                    display_filename = attachment_original_name if attachment_original_name else attachment_filename
                    part.add_header('Content-Disposition', f'attachment; filename="{display_filename}"')
                    msg.attach(part)
                
                # Send the email
                text = msg.as_string()
                server.sendmail(login_acc, email, text)
                sent_emails.append(email)
                
            except Exception as e:
                logging.error(f"Failed to send email to {email}: {str(e)}")
                failed_emails.append({
                    'email': email,
                    'error': str(e)
                })
        
        server.quit()
        
        return {
            "success": True,
            "sent_count": len(sent_emails),
            "failed_count": len(failed_emails),
            "sent_emails": sent_emails,
            "failed_emails": failed_emails
        }
        
    except Exception as e:
        logging.error(f"Email sending error: {str(e)}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Fehler beim E-Mail-Versand: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
