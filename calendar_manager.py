import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import json

logger = logging.getLogger(__name__)

class CalendarManager:
    def __init__(self, db_path="local_data/calendar.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Create tables if not exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS appointments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        description TEXT,
                        start_datetime TIMESTAMP NOT NULL,
                        end_datetime TIMESTAMP NOT NULL,
                        attendees TEXT,
                        status TEXT DEFAULT 'confirmed',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        call_log_id INTEGER
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS availability_windows (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        day_of_week INTEGER,
                        start_time TIME,
                        end_time TIME,
                        buffer_minutes INTEGER DEFAULT 15
                    )
                ")
                # Insert default windows if empty
                cur = conn.execute("SELECT COUNT(*) FROM availability_windows")
                if cur.fetchone()[0] == 0:
                    defaults = [(i, '09:00', '17:00', 15) for i in range(5)]
                    conn.executemany(
                        "INSERT INTO availability_windows (day_of_week, start_time, end_time, buffer_minutes) VALUES (?,?,?,?)",
                        defaults
                    )
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database init failed: {e}")
            raise
    
    def _get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def check_availability(self, dt: datetime, duration_minutes: int = 60) -> Dict:
        """Check if slot is free; return suggested alternatives if not."""
        try:
            end_dt = dt + timedelta(minutes=duration_minutes)
            with self._get_connection() as conn:
                # Conflicts
                cur = conn.execute("""
                    SELECT id, title FROM appointments
                    WHERE status != 'cancelled'
                    AND (
                        (start_datetime < ? AND end_datetime > ?)
                        OR (start_datetime < ? AND end_datetime > ?)
                        OR (start_datetime >= ? AND end_datetime <= ?)
                    )
                """, (end_dt.isoformat(), dt.isoformat(),
                      end_dt.isoformat(), dt.isoformat(),
                      dt.isoformat(), end_dt.isoformat()))
                conflicts = cur.fetchall()
                
                if not conflicts:
                    return {"available": True, "conflicts": [], "suggested_times": []}
                
                # Suggest next available slots
                suggestions = self._suggest_alternatives(dt, duration_minutes, conn)
                return {
                    "available": False,
                    "conflicts": [{"id": c[0], "title": c[1]} for c in conflicts],
                    "suggested_times": [s.isoformat() for s in suggestions]
                }
        except sqlite3.Error as e:
            logger.error(f"Availability check failed: {e}")
            return {"available": False, "error": str(e)}
    
    def _suggest_alternatives(self, preferred: datetime, duration: int, conn, limit=3) -> List[datetime]:
        """Find next free slots."""
        suggestions = []
        check = preferred + timedelta(hours=1)
        while len(suggestions) < limit and check < preferred + timedelta(days=7):
            end_check = check + timedelta(minutes=duration)
            cur = conn.execute("""
                SELECT 1 FROM appointments
                WHERE status != 'cancelled'
                AND (
                    (start_datetime < ? AND end_datetime > ?)
                    OR (start_datetime < ? AND end_datetime > ?)
                )
            """, (end_check.isoformat(), check.isoformat(),
                  end_check.isoformat(), check.isoformat()))
            if not cur.fetchone():
                suggestions.append(check)
            check += timedelta(hours=1)
        return suggestions
    
    def book_appointment(self, title: str, start_datetime: datetime, duration: int,
                         attendees: List[str] = None, **kwargs) -> Dict:
        """Create appointment; return success/failure."""
        try:
            # Re-check availability to avoid race
            avail = self.check_availability(start_datetime, duration)
            if not avail["available"]:
                return {"success": False, "message": "Slot not available", "conflicts": avail["conflicts"]}
            
            end_dt = start_datetime + timedelta(minutes=duration)
            with self._get_connection() as conn:
                cur = conn.execute("""
                    INSERT INTO appointments
                    (title, description, start_datetime, end_datetime, attendees, created_by, call_log_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    title,
                    kwargs.get("description", ""),
                    start_datetime.isoformat(),
                    end_dt.isoformat(),
                    json.dumps(attendees or []),
                    kwargs.get("created_by", "system"),
                    kwargs.get("call_log_id")
                ))
                appt_id = cur.lastrowid
                conn.commit()
                logger.info(f"Appointment booked: ID {appt_id} at {start_datetime}")
                return {
                    "success": True,
                    "appointment_id": appt_id,
                    "message": f"Booked for {start_datetime.strftime('%B %d at %I:%M %p')}"
                }
        except sqlite3.Error as e:
            logger.error(f"Booking failed: {e}")
            return {"success": False, "error": str(e)}
