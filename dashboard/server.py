"""
Rover Network Agent — Analytics Dashboard Backend
Serves API endpoints + static dashboard HTML
"""

import sqlite3
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

# Paths
BASE_DIR = Path(__file__).parent.parent
ANALYTICS_DB = BASE_DIR / "logs" / "analytics.db"
CONVERSATIONS_DB = BASE_DIR / "data" / "conversations.db"
INTERACTIONS_DB = BASE_DIR / "data" / "interactions.db"
DASHBOARD_DIR = Path(__file__).parent

# Add parent to path for imports
sys.path.insert(0, str(BASE_DIR))


def query_db(db_path, sql, params=()):
    """Execute a query and return results as list of dicts."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"DB error ({db_path.name}): {e}")
        return []
    finally:
        conn.close()


def get_overview():
    """Get general overview stats."""
    ops = query_db(ANALYTICS_DB, "SELECT COUNT(*) as total, status FROM operations GROUP BY status")
    total_ops = sum(r['total'] for r in ops)
    successful = sum(r['total'] for r in ops if r['status'] == 'success')
    failed = sum(r['total'] for r in ops if r['status'] != 'success')
    
    convos = query_db(CONVERSATIONS_DB, "SELECT COUNT(DISTINCT user_id) as users, COUNT(*) as messages FROM conversations")
    interactions = query_db(INTERACTIONS_DB, "SELECT COUNT(*) as total, COUNT(DISTINCT contact_name) as contacts FROM interactions")
    
    features = query_db(ANALYTICS_DB, "SELECT feature_name, usage_count, success_count, failure_count FROM feature_usage ORDER BY usage_count DESC LIMIT 10")
    
    return {
        "total_operations": total_ops,
        "successful_operations": successful,
        "failed_operations": failed,
        "total_users": convos[0]['users'] if convos else 0,
        "total_messages": convos[0]['messages'] if convos else 0,
        "total_interactions": interactions[0]['total'] if interactions else 0,
        "unique_contacts": interactions[0]['contacts'] if interactions else 0,
        "top_features": features,
    }


def get_operations_timeline():
    """Get operations over time (last 7 days, hourly buckets)."""
    rows = query_db(ANALYTICS_DB, """
        SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour, 
               COUNT(*) as count, 
               AVG(duration_ms) as avg_duration,
               status
        FROM operations 
        WHERE timestamp >= datetime('now', '-7 days')
        GROUP BY hour, status
        ORDER BY hour
    """)
    return rows


def get_agent_activity():
    """Get agent activity breakdown."""
    tools = query_db(ANALYTICS_DB, """
        SELECT tool_used, COUNT(*) as count, 
               AVG(duration_ms) as avg_duration,
               SUM(success) as successes,
               COUNT(*) - SUM(success) as failures
        FROM agent_activity 
        WHERE tool_used IS NOT NULL
        GROUP BY tool_used 
        ORDER BY count DESC
    """)
    
    recent = query_db(ANALYTICS_DB, """
        SELECT agent_name, action, tool_used, timestamp, duration_ms, success
        FROM agent_activity 
        ORDER BY timestamp DESC 
        LIMIT 20
    """)
    
    return {"tool_usage": tools, "recent_activity": recent}


def get_conversations_stats():
    """Get conversation statistics."""
    by_user = query_db(CONVERSATIONS_DB, """
        SELECT user_id, COUNT(*) as message_count, 
               MIN(timestamp) as first_msg, 
               MAX(timestamp) as last_msg
        FROM conversations 
        GROUP BY user_id 
        ORDER BY message_count DESC 
        LIMIT 20
    """)
    
    by_role = query_db(CONVERSATIONS_DB, """
        SELECT role, COUNT(*) as count 
        FROM conversations 
        GROUP BY role
    """)
    
    recent = query_db(CONVERSATIONS_DB, """
        SELECT user_id, role, 
               SUBSTR(content, 1, 100) as preview, 
               timestamp
        FROM conversations 
        ORDER BY timestamp DESC 
        LIMIT 30
    """)
    
    hourly = query_db(CONVERSATIONS_DB, """
        SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
        FROM conversations
        GROUP BY hour
        ORDER BY hour
    """)
    
    return {
        "by_user": by_user,
        "by_role": by_role,
        "recent_messages": recent,
        "hourly_distribution": hourly,
    }


def get_interactions_stats():
    """Get interaction tracking statistics."""
    by_type = query_db(INTERACTIONS_DB, """
        SELECT interaction_type, COUNT(*) as count
        FROM interactions
        GROUP BY interaction_type
        ORDER BY count DESC
    """)
    
    by_contact = query_db(INTERACTIONS_DB, """
        SELECT contact_name, COUNT(*) as interaction_count,
               MAX(timestamp) as last_interaction,
               MIN(timestamp) as first_interaction
        FROM interactions
        GROUP BY contact_name
        ORDER BY interaction_count DESC
        LIMIT 20
    """)
    
    timeline = query_db(INTERACTIONS_DB, """
        SELECT strftime('%Y-%m-%d', timestamp) as day, COUNT(*) as count
        FROM interactions
        WHERE timestamp >= datetime('now', '-30 days')
        GROUP BY day
        ORDER BY day
    """)
    
    return {
        "by_type": by_type,
        "by_contact": by_contact,
        "timeline": timeline,
    }


def get_errors():
    """Get recent errors."""
    return query_db(ANALYTICS_DB, """
        SELECT error_type, error_message, timestamp, agent_name, resolved
        FROM error_logs
        ORDER BY timestamp DESC
        LIMIT 20
    """)


def get_airtable_contacts():
    """Try to fetch contacts from Airtable."""
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
        from pyairtable import Api
        
        pat = os.getenv("AIRTABLE_PAT", "")
        base_id = os.getenv("AIRTABLE_BASE_ID", "")
        table_name = os.getenv("AIRTABLE_CONTACTS_TABLE", "Contacts")
        
        if not pat or not base_id:
            return {"error": "Airtable not configured", "contacts": []}
        
        api = Api(pat)
        table = api.table(base_id, table_name)
        records = table.all()
        
        contacts = []
        classifications = {}
        relationship_scores = []
        needs_followup = []
        
        for r in records:
            fields = r.get("fields", {})
            contact = {
                "id": r["id"],
                "name": fields.get("Name", "Unknown"),
                "classification": fields.get("Classification", "unclassified"),
                "company": fields.get("Company", ""),
                "relationship_score": fields.get("relationship_score", 0),
                "relationship_stage": fields.get("relationship_stage", "new"),
                "last_interaction": fields.get("last_interaction_date", ""),
                "follow_up_date": fields.get("follow_up_date", ""),
                "follow_up_reason": fields.get("follow_up_reason", ""),
                "interaction_count": fields.get("interaction_count", 0),
                "priority": fields.get("priority", "normal"),
            }
            contacts.append(contact)
            
            cls = contact["classification"]
            classifications[cls] = classifications.get(cls, 0) + 1
            
            if contact["relationship_score"]:
                relationship_scores.append(contact["relationship_score"])
            
            if contact["follow_up_date"]:
                needs_followup.append(contact)
        
        # Score distribution buckets
        score_dist = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
        for s in relationship_scores:
            if s <= 20: score_dist["0-20"] += 1
            elif s <= 40: score_dist["21-40"] += 1
            elif s <= 60: score_dist["41-60"] += 1
            elif s <= 80: score_dist["61-80"] += 1
            else: score_dist["81-100"] += 1
        
        return {
            "total": len(contacts),
            "classifications": classifications,
            "score_distribution": score_dist,
            "avg_score": sum(relationship_scores) / len(relationship_scores) if relationship_scores else 0,
            "needs_followup": len(needs_followup),
            "contacts": sorted(contacts, key=lambda x: x.get("relationship_score", 0) or 0, reverse=True)[:30],
            "followups": sorted(needs_followup, key=lambda x: x.get("follow_up_date", "")),
        }
    except Exception as e:
        return {"error": str(e), "contacts": []}


class DashboardHandler(SimpleHTTPRequestHandler):
    """Custom handler for dashboard API + static files."""
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path.startswith("/api/"):
            self.handle_api(path)
        elif path == "/" or path == "/index.html":
            self.serve_file("index.html", "text/html")
        else:
            # Serve static files from dashboard dir
            super().do_GET()
    
    def handle_api(self, path):
        endpoints = {
            "/api/overview": get_overview,
            "/api/operations": get_operations_timeline,
            "/api/agent": get_agent_activity,
            "/api/conversations": get_conversations_stats,
            "/api/interactions": get_interactions_stats,
            "/api/errors": get_errors,
            "/api/contacts": get_airtable_contacts,
        }
        
        handler = endpoints.get(path)
        if handler:
            try:
                data = handler()
                self.send_json(data)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
        else:
            self.send_json({"error": "Not found"}, 404)
    
    def send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())
    
    def serve_file(self, filename, content_type):
        filepath = DASHBOARD_DIR / filename
        if filepath.exists():
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(filepath.read_bytes())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress access logs


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    os.chdir(str(DASHBOARD_DIR))
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"🚀 Rover Dashboard running at http://localhost:{port}")
    server.serve_forever()
