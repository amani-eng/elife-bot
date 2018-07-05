"provider for sending email"
import os
import smtplib
import traceback
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import boto.ses


def ses_connect(settings):
    "connect to SES"
    return boto.ses.connect_to_region(
        settings.ses_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key)


def smtp_connect(settings, logger=None):
    "connect to SMTP"
    smtp_host = settings.smtp_host
    smtp_port = settings.smtp_port
    smtp_starttls = settings.smtp_starttls
    smtp_ssl = settings.smtp_ssl
    smtp_user = settings.smtp_user
    smtp_password = settings.smtp_password
    try:
        connection = (smtplib.SMTP_SSL(smtp_host, smtp_port)
                      if smtp_ssl else smtplib.SMTP(smtp_host, smtp_port))
    except:
        connection = None
        if logger:
            logger.error('error in smtp_connect: %s ', traceback.format_exc())
    if smtp_starttls:
        connection.starttlconnection()
    if smtp_user and smtp_password:
        connection.login(smtp_user, smtp_password)
    return connection


def attachment(file_name,
               media_type='vnd.openxmlformats-officedocument.wordprocessingml.document',
               charset='UTF-8'):
    "create an attachment from the file"
    content_type_header = '{media_type}; charset={charset}'.format(
        media_type=media_type, charset=charset)
    attachment_name = os.path.split(file_name)[-1]
    with open(file_name, 'rb') as open_file:
        email_attachment = MIMEApplication(open_file.read())
    email_attachment.add_header('Content-Disposition', 'attachment', filename=attachment_name)
    email_attachment.add_header('Content-Type', content_type_header)
    return email_attachment


def add_attachment(message, file_name,
                   media_type='vnd.openxmlformats-officedocument.wordprocessingml.document',
                   charset='UTF-8'):
    "add an attachment to the message"
    email_attachment = attachment(file_name, media_type, charset)
    message.attach(email_attachment)


def add_text(message, text):
    "add text to the message"
    message.attach(MIMEText(text))


def message(subject, sender, recipient):
    "create an email message to later attach things to"
    message = MIMEMultipart()
    message['Subject'] = subject
    message['From'] = sender
    message['To'] = recipient
    return message


def ses_send(connection, sender, recipient, message):
    "send a MIMEMultipart email to the recipient from sender"
    return connection.send_raw_email(message.as_string(), source=sender, destinations=recipient)


def smtp_send(connection, sender, recipient, message):
    "send a MIMEMultipart email to the recipient from sender by SMTP"
    connection.sendmail(sender, recipient, message.as_string())
