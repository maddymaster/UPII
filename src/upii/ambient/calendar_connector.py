import os
import re
import datetime
import uuid
from typing import List, Dict, Generator
from upii.core.logger import logger
from upii.storage.db import DB

class CalendarConnector:
    """
    Parses .ics files and ingests metadata into LTM.
    Focus: Title, Start, End, Participants.
    """
    
    def __init__(self):
        self.db = DB()
        
    def process_file(self, file_path: str) -> int:
        """Parses an ICS file and saves events. Returns count."""
        if not os.path.exists(file_path):
            logger.error(f"Calendar file not found: {file_path}")
            return 0
            
        count = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            events = self._parse_ics(content)
            self.db.init_db()
            
            for event in events:
                event['source_file'] = os.path.basename(file_path)
                self.db.add_calendar_event(event)
                count += 1
                
            logger.info(f"Ingested {count} calendar events from {file_path}")
        except Exception as e:
            logger.error(f"Failed to process calendar {file_path}: {e}")
            
        return count

    def _parse_ics(self, content: str) -> List[Dict]:
        """
        Robust-ish Regex parser for ICS. 
        (Production would use `icalendar` lib, but we avoid deps here).
        """
        events = []
        # Split by VEVENT
        raw_events = re.findall(r'BEGIN:VEVENT(.*?)END:VEVENT', content, re.DOTALL)
        
        for raw in raw_events:
            try:
                # 1. Title (SUMMARY)
                summary_match = re.search(r'SUMMARY:(.*)', raw)
                title = summary_match.group(1).strip() if summary_match else "Untitled Event"
                
                # 2. Date (DTSTART/DTEND)
                # Formats: 20230101T120000Z or ;TZID=...:2023...
                dtstart_match = re.search(r'DTSTART.*?:(\d{8}T\d{6}Z|\d{8}T\d{6}|\d{8})', raw)
                dtend_match = re.search(r'DTEND.*?:(\d{8}T\d{6}Z|\d{8}T\d{6}|\d{8})', raw)
                
                start_str = dtstart_match.group(1) if dtstart_match else None
                end_str = dtend_match.group(1) if dtend_match else None
                
                if not start_str: continue # Skip if no time
                
                # Normalize Time
                start_time = self._parse_ical_date(start_str)
                end_time = self._parse_ical_date(end_str) if end_str else start_time
                
                # 3. Participants (ATTENDEE)
                # ATTENDEE;CN="Alice Smith":mailto:alice@example.com
                attendees = []
                for line in raw.split('\n'):
                    if line.startswith('ATTENDEE'):
                        # Extract email or CN
                        if 'mailto:' in line:
                            email = line.split('mailto:')[-1].strip()
                            attendees.append(email)
                        elif 'CN=' in line:
                            cn = line.split('CN=')[1].split(':')[0].replace('"','').strip()
                            attendees.append(cn)
                
                events.append({
                    "event_id": str(uuid.uuid4()),
                    "title": title,
                    "start_time": start_time,
                    "end_time": end_time,
                    "participants": attendees
                })
                
            except Exception as e:
                logger.warning(f"Failed to parse event: {e}")
                
        return events

    def _parse_ical_date(self, date_str: str) -> str:
        """Converts ICS date/datetime to ISO8601 string."""
        # YYYYMMDD
        if len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}T00:00:00"
        
        # YYYYMMDDTHHMMSS(Z)
        clean = date_str.replace('Z', '')
        return f"{clean[:4]}-{clean[4:6]}-{clean[6:8]}T{clean[9:11]}:{clean[11:13]}:{clean[13:]}"
