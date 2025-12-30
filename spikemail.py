import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURATION ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
GMAIL_USER = os.environ.get('EMAIL')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD')

# THE ADDRESS YOU WANT TO APPEAR AS
FROM_EMAIL = "minecraft@spikenet.net"


def send_email(email, subject, body):
    # Create the email container
    msg = MIMEMultipart()
    msg['From'] = FROM_EMAIL
    msg['To'] = email
    msg['Subject'] = subject

    # Attach the body text
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect to Gmail's SMTP server
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # Upgrade the connection to secure
        
        # Login using your REAL Gmail and the App Password
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        
        # Send the email
        server.send_message(msg)
        server.quit()
        print("Successfully sent email")
        
    except Exception as e:
        print(f"Error: {e}")

