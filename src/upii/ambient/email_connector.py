import mailbox
import os
import email
from email.header import decode_header
from typing import Generator, Dict, Any
from upii.core.logger import logger

class EmailConnector:
    """
    Parses email files (.mbox, .eml) and extracts content.
    """
    
    @staticmethod
    def parse_mbox(file_path: str) -> Generator[Dict[str, Any], None, None]:
        """Parses an MBOX file and yields email data dictionaries."""
        if not os.path.exists(file_path):
            logger.error(f"Mbox file not found: {file_path}")
            return

        try:
            mbox = mailbox.mbox(file_path)
            for message in mbox:
                try:
                    yield EmailConnector._extract_message_data(message, file_path)
                except Exception as e:
                    logger.warning(f"Failed to parse email message: {e}")
        except Exception as e:
            logger.error(f"Failed to open mbox {file_path}: {e}")

    @staticmethod
    def _extract_message_data(msg, source_file: str) -> Dict[str, Any]:
        """Extracts title, sender, date, and body from an email message."""
        
        def decode_str(s):
            if not s: return ""
            try:
                decoded_list = decode_header(s)
                return "".join([
                    (t[0].decode(t[1] or 'utf-8') if isinstance(t[0], bytes) else t[0]) 
                    for t in decoded_list
                ])
            except:
                return str(s)

        subject = decode_str(msg.get('subject', 'No Subject'))
        sender = decode_str(msg.get('from', 'Unknown'))
        date = msg.get('date', '')
        
        # Body extraction
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except: pass
        else:
            try:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            except: pass

        return {
            "title": subject,
            "sender": sender,
            "date": date,
            "content": f"From: {sender}\nDate: {date}\nSubject: {subject}\n\n{body}",
            "source_type": "email",
             # We might want a unique ID for the email if available, else random
            "email_id": msg.get('Message-ID', ''),
            "source_file": source_file
        }
