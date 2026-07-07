from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
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

app = FastAPI(title="Attachments Mailer", description="Email Versand Tool")

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
        if not all([email_login, smtp_server]):
            raise HTTPException(status_code=400, detail="SMTP-Server und E-Mail-Adresse sind erforderlich")
        
        # Test SMTP connection
        try:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            if email_password:
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

@app.post("/upload-data-file")
async def upload_data_file(request: Request, file: UploadFile = File(...)):
    """Upload CSV or XLSX file and return columns for selection"""
    try:
        session_id = get_session_id(request)
        session = user_sessions[session_id]
        
        contents = await file.read()
        
        # Determine file type and read accordingly
        if file.filename.lower().endswith('.csv'):
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        elif file.filename.lower().endswith('.xlsx'):
            # Use openpyxl engine for .xlsx files
            df = pd.read_excel(io.BytesIO(contents), engine='openpyxl')
        elif file.filename.lower().endswith('.xls'):
            # Use xlrd engine for .xls files
            df = pd.read_excel(io.BytesIO(contents), engine='xlrd')
        else:
            raise HTTPException(status_code=400, detail="Nur CSV-, XLSX- und XLS-Dateien werden unterstützt")
        
        # Clean the dataframe: replace NaN values with empty strings and convert to string
        df = df.fillna('')
        df = df.astype(str)
        
        # Store original dataframe in session
        session["original_dataframe"] = df.to_dict('records')
        session["dataframe_columns"] = list(df.columns)
        
        # Return columns for selection and preview data (first 5 rows)
        preview_data = df.head(5).to_dict('records')
        
        return {
            "success": True, 
            "columns": list(df.columns),
            "preview_data": preview_data,
            "total_rows": len(df),
            "filename": file.filename
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Lesen der Datei: {str(e)}")

@app.post("/select-columns")
async def select_columns(request: Request):
    """Process column selection and create final data structure"""
    try:
        session_id = get_session_id(request)
        session = user_sessions[session_id]
        
        data = await request.json()
        email_column = data.get('email_column')
        attachment_column = data.get('attachment_column')
        placeholder_columns = data.get('placeholder_columns', {})  # Dict mapping placeholder names to column names
        
        if not email_column or not attachment_column:
            raise HTTPException(status_code=400, detail="Email- und Anhang-Spalten müssen ausgewählt werden")
        
        # Get original dataframe
        original_data = session.get("original_dataframe", [])
        if not original_data:
            raise HTTPException(status_code=400, detail="Keine Daten verfügbar. Bitte laden Sie zuerst eine Datei hoch.")
        
        # Create processed data with selected columns
        processed_data = []
        for row in original_data:
            email_value = row.get(email_column, '').strip()
            attachment_value = row.get(attachment_column, '').strip()
            
            # Include ALL rows, even those with empty values
            # Clean up 'nan' values from pandas
            if email_value == 'nan':
                email_value = ''
            if attachment_value == 'nan':
                attachment_value = ''
            
            row_data = {
                "emails": email_value,
                "attachments": attachment_value
            }
            
            # Add placeholder values
            for placeholder_name, column_name in placeholder_columns.items():
                if column_name and column_name in row:
                    placeholder_value = row.get(column_name, '').strip()
                    row_data[placeholder_name] = placeholder_value if placeholder_value != 'nan' else ''
                else:
                    row_data[placeholder_name] = ''
            
            processed_data.append(row_data)
        
        # Store processed data in session
        session["csv_data"] = processed_data
        session["selected_columns"] = {
            "email_column": email_column,
            "attachment_column": attachment_column,
            "placeholder_columns": placeholder_columns
        }
        
        return {
            "success": True, 
            "data": processed_data,
            "processed_count": len(processed_data)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler bei der Spaltenverarbeitung: {str(e)}")

@app.post("/update-table-data")
async def update_table_data(request: Request):
    """Update table data from frontend edits"""
    try:
        session_id = get_session_id(request)
        session = user_sessions[session_id]
        
        data = await request.json()
        table_data = data.get('table_data', [])
        
        # Validate data structure
        for row in table_data:
            if not row.get('emails') or not row.get('attachments'):
                continue  # Skip empty rows
            
        # Store updated data in session
        session["csv_data"] = [row for row in table_data if row.get('emails') and row.get('attachments')]
        
        return {
            "success": True, 
            "updated_count": len(session["csv_data"])
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Aktualisieren der Tabellendaten: {str(e)}")

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
        
        # Return original filenames for frontend processing
        original_filenames = [item["original_name"] for item in uploaded_files]
        
        return {"success": True, "uploaded_files": original_filenames}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Hochladen der Anhänge: {str(e)}")

@app.get("/list-attachments")
async def list_attachments(request: Request):
    """List uploaded attachments for current session"""
    try:
        session_id = get_session_id(request)
        session = user_sessions[session_id]
        
        attachments = session.get("attachments", {})
        file_list = [info["original_name"] for info in attachments.values()]
        
        return {
            "success": True,
            "files": file_list,
            "count": len(file_list)
        }
        
    except Exception as e:
        logging.error(f"List attachments error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing attachments: {str(e)}")

@app.delete("/remove-attachment")
async def remove_attachment(request: Request):
    """Remove a specific attachment by filename"""
    try:
        session_id = get_session_id(request)
        session = user_sessions[session_id]
        
        body = await request.json()
        filename = body.get("filename")
        
        if not filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        
        attachments = session.get("attachments", {})
        
        # Find attachment by original name
        attachment_to_remove = None
        for unique_name, info in attachments.items():
            if info["original_name"] == filename:
                attachment_to_remove = unique_name
                break
        
        if not attachment_to_remove:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Remove file from filesystem
        file_path = attachments[attachment_to_remove]["path"]
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Remove from session
        del attachments[attachment_to_remove]
        
        return {
            "success": True,
            "message": f"File '{filename}' removed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Remove attachment error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error removing attachment: {str(e)}")

@app.delete("/remove-all-attachments")
async def remove_all_attachments(request: Request):
    """Remove all attachments for current session"""
    try:
        session_id = get_session_id(request)
        session = user_sessions[session_id]
        
        attachments = session.get("attachments", {})
        removed_count = len(attachments)
        
        # Remove all files from filesystem
        for unique_name, info in attachments.items():
            file_path = info["path"]
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Clear attachments from session
        session["attachments"] = {}
        
        return {
            "success": True,
            "message": f"Removed {removed_count} attachments successfully",
            "removed_count": removed_count
        }
        
    except Exception as e:
        logging.error(f"Remove all attachments error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error removing all attachments: {str(e)}")

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
        
        # Helper function to find attachment
        def find_attachment(attachment_filename, session_attachments):
            for filename, file_data in session_attachments.items():
                original_name = file_data["original_name"]
                if (original_name == attachment_filename or
                    os.path.splitext(original_name)[0] == os.path.splitext(attachment_filename)[0] or
                    attachment_filename + '.pdf' == original_name or
                    os.path.splitext(original_name)[0] == attachment_filename):
                    return True, original_name
            return False, None
        
        valid_emails = []
        invalid_emails = []
        
        for row in csv_data:
            email = row['emails']
            attachment_field = row['attachments']
            
            # Parse multiple attachments (separated by newlines or commas)
            attachment_names = [name.strip() for name in attachment_field.replace('\r\n', '\n').replace(',', '\n').split('\n') if name.strip()]
            
            found_attachments = []
            missing_attachments = []
            
            for attachment_filename in attachment_names:
                attachment_found, found_name = find_attachment(attachment_filename, session.get("attachments", {}))
                if attachment_found:
                    found_attachments.append(found_name)
                else:
                    missing_attachments.append(attachment_filename)
            
            if found_attachments and not missing_attachments:
                # All attachments found
                valid_emails.append({
                    'email': email,
                    'attachment': ', '.join(found_attachments),
                    'attachment_count': len(found_attachments),
                    'status': 'valid'
                })
            elif found_attachments and missing_attachments:
                # Some attachments found, some missing - still add to valid but note
                valid_emails.append({
                    'email': email,
                    'attachment': ', '.join(found_attachments),
                    'attachment_count': len(found_attachments),
                    'missing': ', '.join(missing_attachments),
                    'status': 'partial'
                })
            else:
                # No attachments found
                invalid_emails.append({
                    'email': email,
                    'attachment': ', '.join(missing_attachments),
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
        if not all([login_acc, smtp_server, email_subject]):
            raise HTTPException(status_code=400, detail="E-Mail-Adresse, SMTP-Server und Betreff sind erforderlich")
        
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
        
        # Helper function to find attachment in session
        def find_attachment(attachment_filename, session_attachments):
            for filename, file_data in session_attachments.items():
                original_name = file_data["original_name"]
                
                # Strategy 1: Exact match with original name
                if original_name == attachment_filename:
                    return file_data["path"], original_name
                
                # Strategy 2: Match with filename (no extension) from CSV
                original_name_no_ext = os.path.splitext(original_name)[0]
                attachment_no_ext = os.path.splitext(attachment_filename)[0]
                if original_name_no_ext == attachment_no_ext:
                    return file_data["path"], original_name
                
                # Strategy 3: Check if CSV entry matches filename with .pdf extension
                if attachment_filename + '.pdf' == original_name:
                    return file_data["path"], original_name
                
                # Strategy 4: Check if original name without extension matches CSV entry
                if original_name_no_ext == attachment_filename:
                    return file_data["path"], original_name
            
            return None, None
        
        # Connect to SMTP server
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        if login_pass:
            server.login(login_acc, login_pass)
        
        sent_emails = []
        failed_emails = []
        
        for row in csv_data:
            try:
                email = row['emails']
                attachment_field = row['attachments']
                
                # Parse multiple attachments (separated by newlines or commas)
                attachment_names = [name.strip() for name in attachment_field.replace('\r\n', '\n').replace(',', '\n').split('\n') if name.strip()]
                
                # Find all attachments
                found_attachments = []
                missing_attachments = []
                
                for attachment_filename in attachment_names:
                    attachment_path, attachment_original_name = find_attachment(attachment_filename, session.get("attachments", {}))
                    
                    if attachment_path and os.path.exists(attachment_path):
                        found_attachments.append({
                            'path': attachment_path,
                            'original_name': attachment_original_name,
                            'requested_name': attachment_filename
                        })
                    else:
                        missing_attachments.append(attachment_filename)
                
                # Skip if no attachments found
                if not found_attachments:
                    failed_emails.append({
                        'email': email,
                        'error': f'Keine Anhänge gefunden: {", ".join(missing_attachments)}'
                    })
                    continue
                
                # Log warning if some attachments are missing but we have at least one
                if missing_attachments:
                    logging.warning(f"Email to {email}: Some attachments missing: {missing_attachments}, proceeding with found attachments: {[a['original_name'] for a in found_attachments]}")
                
                # Create a new message for each email
                msg = MIMEMultipart()
                msg['From'] = login_acc
                msg['To'] = email
                msg['Subject'] = email_subject
                
                # Process email body to replace image references and attach images
                processed_email_body = email_body
                
                # Replace placeholders with values from CSV data
                for key, value in row.items():
                    if key not in ['emails', 'attachments']:  # Skip standard fields
                        placeholder = f"[{key}]"
                        if placeholder in processed_email_body:
                            processed_email_body = processed_email_body.replace(placeholder, str(value))
                            logging.info(f"Replaced placeholder {placeholder} with '{value}' for {email}")
                
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
                                image_data = img.read()
                                image = MIMEImage(image_data)
                                image.add_header('Content-ID', f'<{image_cid}>')
                                image.add_header('Content-Disposition', 'inline', filename=original_name)
                                msg.attach(image)
                                logging.info(f"Attached image {original_name} with CID {image_cid} to email for {email}")
                                
                    except Exception as img_err:
                        logging.error(f"Failed to attach image {filename}: {str(img_err)}")
                
                # Attach the processed email body
                msg.attach(MIMEText(processed_email_body, 'html'))
                
                # Attach all found attachments
                for attachment_info in found_attachments:
                    attachment_path = attachment_info['path']
                    attachment_original_name = attachment_info['original_name']
                    
                    with open(attachment_path, 'rb') as attachment_file:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment_file.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename="{attachment_original_name}"')
                        msg.attach(part)
                    
                    logging.info(f"Attached file {attachment_original_name} to email for {email}")
                
                # Send the email
                text = msg.as_string()
                server.sendmail(login_acc, email, text)
                sent_emails.append(email)
                logging.info(f"Successfully sent email to {email} with {len(found_attachments)} attachment(s)")
                
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
