"""
Rover Network Agent — Analytics Dashboard Backend v2
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

sys.path.insert(0, str(BASE_DIR))


def query_db(db_path, sql, params=()):
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
    ops = query_db(ANALYTICS_DB, "SELECT COUNT(*) as total, status FROM operations GROUP BY status")
    total_ops = sum(r['total'] for r in ops)
    successful = sum(r['total'] for r in ops if r['status'] == 'success')
    failed = sum(r['total'] for r in ops if r['status'] != 'success')
    convos = query_db(CONVERSATIONS_DB, "SELECT COUNT(DISTINCT user_id) as users, COUNT(*) as messages FROM conversations")
    interactions = query_db(INTERACTIONS_DB, "SELECT COUNT(*) as total, COUNT(DISTINCT contact_name) as contacts FROM interactions")
    
    # Follow-ups
    follow_ups = query_db(INTERACTIONS_DB, "SELECT COUNT(*) as total FROM follow_ups WHERE completed = 0")
    
    return {
        "total_operations": total_ops,
        "successful_operations": successful,
        "failed_operations": failed,
        "total_users": convos[0]['users'] if convos else 0,
        "total_messages": convos[0]['messages'] if convos else 0,
        "total_interactions": interactions[0]['total'] if interactions else 0,
        "unique_contacts": interactions[0]['contacts'] if interactions else 0,
        "pending_follow_ups": follow_ups[0]['total'] if follow_ups else 0,
    }


def get_contacts():
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
        from pyairtable import Api
        
        pat = os.getenv("AIRTABLE_PAT", "")
        base_id = os.getenv("AIRTABLE_BASE_ID", "")
        
        if not pat or not base_id:
            return {"error": "Airtable not configured", "contacts": []}
        
        api = Api(pat)
        table = api.table(base_id, os.getenv("AIRTABLE_CONTACTS_TABLE", "Contacts"))
        records = table.all()
        
        contacts = []
        classifications = {}
        stages = {}
        priorities = {}
        industries = {}
        scores = []
        
        for r in records:
            f = r.get("fields", {})
            contact = {
                "id": r["id"],
                "name": f.get("full_name") or f.get("first_name", "Unknown"),
                "title": f.get("title", ""),
                "company": f.get("company", ""),
                "email": f.get("email", ""),
                "phone": f.get("phone", ""),
                "classification": f.get("contact_type", "unclassified"),
                "industry": f.get("industry", ""),
                "relationship_score": f.get("relationship_score", 0),
                "relationship_stage": f.get("relationship_stage", "new"),
                "interaction_count": f.get("interaction_count", 0),
                "last_interaction": f.get("last_interaction_date", ""),
                "follow_up_date": f.get("follow_up_date", ""),
                "follow_up_reason": f.get("follow_up_reason", ""),
                "priority": f.get("priority", ""),
                "introduced_by": f.get("introduced_by", ""),
                "introduced_to": f.get("introduced_to", ""),
                "linkedin": f.get("contact_linkedin_url", ""),
                "source": f.get("source", ""),
                "created": f.get("created_date", ""),
            }
            contacts.append(contact)
            
            cls = contact["classification"] or "unclassified"
            classifications[cls] = classifications.get(cls, 0) + 1
            
            stage = contact["relationship_stage"] or "new"
            stages[stage] = stages.get(stage, 0) + 1
            
            if contact["priority"]:
                priorities[contact["priority"]] = priorities.get(contact["priority"], 0) + 1
            
            if contact["industry"]:
                for ind in contact["industry"].split(","):
                    ind = ind.strip()
                    if ind:
                        industries[ind] = industries.get(ind, 0) + 1
            
            if contact["relationship_score"]:
                scores.append(contact["relationship_score"])
        
        score_dist = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
        for s in scores:
            if s <= 20: score_dist["0-20"] += 1
            elif s <= 40: score_dist["21-40"] += 1
            elif s <= 60: score_dist["41-60"] += 1
            elif s <= 80: score_dist["61-80"] += 1
            else: score_dist["81-100"] += 1
        
        # Contacts needing attention (follow-up overdue or low score)
        today = datetime.now().strftime("%Y-%m-%d")
        needs_attention = [c for c in contacts if 
            (c["follow_up_date"] and c["follow_up_date"] <= today) or
            (c["relationship_score"] and c["relationship_score"] < 30)]
        
        return {
            "total": len(contacts),
            "classifications": classifications,
            "stages": stages,
            "priorities": priorities,
            "industries": dict(sorted(industries.items(), key=lambda x: -x[1])[:10]),
            "score_distribution": score_dist,
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "needs_attention": len(needs_attention),
            "contacts": sorted(contacts, key=lambda x: x.get("relationship_score") or 0, reverse=True),
        }
    except Exception as e:
        return {"error": str(e), "contacts": []}


def get_introductions():
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
        from pyairtable import Api
        
        api = Api(os.getenv("AIRTABLE_PAT", ""))
        table = api.table(os.getenv("AIRTABLE_BASE_ID", ""), "Introductions")
        records = table.all()
        
        intros = []
        status_counts = {}
        for r in records:
            f = r.get("fields", {})
            intro = {
                "connector": f.get("connector_name", ""),
                "target": f.get("target_name", ""),
                "reason": f.get("reason", ""),
                "status": f.get("status", "suggested"),
                "date": f.get("requested_date", ""),
                "outcome": f.get("outcome", ""),
            }
            intros.append(intro)
            s = intro["status"]
            status_counts[s] = status_counts.get(s, 0) + 1
        
        return {"total": len(intros), "status_counts": status_counts, "introductions": intros}
    except Exception as e:
        return {"error": str(e), "introductions": []}


def get_interactions_stats():
    by_type = query_db(INTERACTIONS_DB, """
        SELECT interaction_type, COUNT(*) as count
        FROM interactions GROUP BY interaction_type ORDER BY count DESC
    """)
    by_contact = query_db(INTERACTIONS_DB, """
        SELECT contact_name, COUNT(*) as interaction_count,
               MAX(timestamp) as last_interaction
        FROM interactions GROUP BY contact_name ORDER BY interaction_count DESC LIMIT 20
    """)
    timeline = query_db(INTERACTIONS_DB, """
        SELECT strftime('%Y-%m-%d', timestamp) as day, COUNT(*) as count
        FROM interactions WHERE timestamp >= datetime('now', '-30 days')
        GROUP BY day ORDER BY day
    """)
    follow_ups = query_db(INTERACTIONS_DB, """
        SELECT contact_name, follow_up_date, reason, completed
        FROM follow_ups ORDER BY follow_up_date ASC
    """)
    
    # Weekly summary
    weekly = query_db(INTERACTIONS_DB, """
        SELECT strftime('%W', timestamp) as week, COUNT(*) as count,
               COUNT(DISTINCT contact_name) as unique_contacts
        FROM interactions WHERE timestamp >= datetime('now', '-8 weeks')
        GROUP BY week ORDER BY week
    """)
    
    return {
        "by_type": by_type,
        "by_contact": by_contact,
        "timeline": timeline,
        "follow_ups": follow_ups,
        "weekly": weekly,
    }


def get_conversations_stats():
    by_role = query_db(CONVERSATIONS_DB, "SELECT role, COUNT(*) as count FROM conversations GROUP BY role")
    hourly = query_db(CONVERSATIONS_DB, """
        SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
        FROM conversations GROUP BY hour ORDER BY hour
    """)
    recent = query_db(CONVERSATIONS_DB, """
        SELECT user_id, role, SUBSTR(content, 1, 100) as preview, timestamp
        FROM conversations ORDER BY timestamp DESC LIMIT 30
    """)
    return {"by_role": by_role, "hourly_distribution": hourly, "recent_messages": recent}


def get_network_intelligence():
    """Network-level insights."""
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / ".env")
        from pyairtable import Api
        
        api = Api(os.getenv("AIRTABLE_PAT", ""))
        table = api.table(os.getenv("AIRTABLE_BASE_ID", ""), os.getenv("AIRTABLE_CONTACTS_TABLE", "Contacts"))
        records = table.all()
        
        contacts = [r.get("fields", {}) for r in records]
        
        # Network health score
        scores = [c.get("relationship_score", 0) for c in contacts if c.get("relationship_score")]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        
        # Diversity index (how spread across industries)
        industries = set()
        for c in contacts:
            if c.get("industry"):
                for i in c["industry"].split(","):
                    industries.add(i.strip().lower())
        
        # Contact growth (by source)
        sources = {}
        for c in contacts:
            s = c.get("source", "unknown")
            sources[s] = sources.get(s, 0) + 1
        
        # Enrichment rate
        enriched = sum(1 for c in contacts if c.get("industry") or c.get("company_description") or c.get("contact_linkedin_url"))
        enrichment_rate = round(enriched / len(contacts) * 100, 1) if contacts else 0
        
        # Has email rate
        has_email = sum(1 for c in contacts if c.get("email"))
        email_rate = round(has_email / len(contacts) * 100, 1) if contacts else 0
        
        # Active vs dormant
        active = sum(1 for c in contacts if c.get("relationship_stage") in ("building", "strong"))
        dormant = sum(1 for c in contacts if c.get("relationship_stage") in ("dormant", "lost"))
        
        return {
            "network_health": avg_score,
            "total_contacts": len(contacts),
            "industries_count": len(industries),
            "sources": sources,
            "enrichment_rate": enrichment_rate,
            "email_rate": email_rate,
            "has_email": has_email,
            "enriched": enriched,
            "active_relationships": active,
            "dormant_relationships": dormant,
        }
    except Exception as e:
        return {"error": str(e)}


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path.startswith("/api/"):
            self.handle_api(path)
        elif path == "/" or path == "/index.html":
            self.serve_file("index.html", "text/html")
        else:
            super().do_GET()
    
    def handle_api(self, path):
        endpoints = {
            "/api/overview": get_overview,
            "/api/contacts": get_contacts,
            "/api/introductions": get_introductions,
            "/api/interactions": get_interactions_stats,
            "/api/conversations": get_conversations_stats,
            "/api/intelligence": get_network_intelligence,
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
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    os.chdir(str(DASHBOARD_DIR))
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"🚀 Rover Dashboard v2 running at http://localhost:{port}")
    server.serve_forever()
