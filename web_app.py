from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import smtplib
import pandas as pd
import os
import io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
import traceback
import logging
from typing import List
import json
from pydantic import BaseModel

app = FastAPI(title="Simple Mailer", description="Email Versand Tool")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        
        # Validate CSV structure
        if 'emails' not in df.columns or 'attachments' not in df.columns:
            raise HTTPException(status_code=400, detail="CSV muss 'emails' und 'attachments' Spalten enthalten")
        
        # Convert to list of dictionaries
        data = df.to_dict('records')
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Lesen der CSV: {str(e)}")

@app.post("/upload-attachments")
async def upload_attachments(files: List[UploadFile] = File(...)):
    try:
        # Create attachments directory if it doesn't exist
        os.makedirs("attachments", exist_ok=True)
        
        uploaded_files = []
        for file in files:
            file_path = os.path.join("attachments", file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            uploaded_files.append(file.filename)
        
        return {"success": True, "uploaded_files": uploaded_files}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Hochladen der Anhänge: {str(e)}")

@app.post("/upload-email-body")
async def upload_email_body(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        email_body = contents.decode('utf-8')
        
        # Save to file
        with open('email_body.html', 'w', encoding='utf-8') as f:
            f.write(email_body)
        
        return {"success": True, "body": email_body}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Hochladen des Email-Body: {str(e)}")

@app.post("/upload-logo")
async def upload_logo(file: UploadFile = File(...)):
    try:
        # Save logo file
        with open('ticketree.png', 'wb') as f:
            content = await file.read()
            f.write(content)
        
        return {"success": True, "message": "Logo erfolgreich hochgeladen"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler beim Hochladen des Logos: {str(e)}")

@app.post("/preview-emails")
async def preview_emails(email_data: dict):
    try:
        csv_data = email_data.get('csv_data', [])
        
        if not csv_data:
            raise HTTPException(status_code=400, detail="Keine CSV-Daten vorhanden")
        
        valid_emails = []
        invalid_emails = []
        
        for row in csv_data:
            email = row['emails']
            attachment_filename = row['attachments'] + '.pdf'
            attachment_path = os.path.join('attachments', attachment_filename)
            
            if os.path.exists(attachment_path):
                valid_emails.append({
                    'email': email,
                    'attachment': attachment_filename,
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
async def send_emails(request_data: dict):
    try:
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
        
        # Read email body
        if not os.path.exists('email_body.html'):
            raise HTTPException(status_code=400, detail="Email-Body (email_body.html) nicht gefunden")
        
        with open('email_body.html', 'r', encoding='utf-8') as f:
            email_body = f.read()
        
        # Connect to SMTP server
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(login_acc, login_pass)
        
        sent_emails = []
        failed_emails = []
        
        for row in csv_data:
            try:
                email = row['emails']
                attachment_filename = row['attachments'] + '.pdf'
                attachment_path = os.path.join('attachments', attachment_filename)
                
                # Skip if attachment doesn't exist
                if not os.path.exists(attachment_path):
                    failed_emails.append({
                        'email': email,
                        'error': 'Anhang nicht gefunden'
                    })
                    continue
                
                # Create a new message for each email
                msg = MIMEMultipart()
                msg['From'] = login_acc
                msg['To'] = email
                msg['Subject'] = email_subject
                
                # Add the logo image as inline attachment if it exists
                if os.path.exists('ticketree.png'):
                    try:
                        with open('ticketree.png', 'rb') as img:
                            image = MIMEImage(img.read())
                            image.add_header('Content-ID', '<ticketree-logo>')
                            image.add_header('Content-Disposition', 'inline', filename='ticketree-logo.png')
                            msg.attach(image)
                    except Exception as img_err:
                        logging.error(f"Failed to attach logo image: {str(img_err)}")
                
                # Attach the email body
                msg.attach(MIMEText(email_body, 'html'))
                
                # Create the attachment for this specific email
                with open(attachment_path, 'rb') as attachment_file:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment_file.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{attachment_filename}"')
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
