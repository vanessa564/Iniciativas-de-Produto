import os
import json
import urllib.request
import urllib.parse
import base64
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
JIRA_DOMAIN  = os.environ["JIRA_DOMAIN"].strip().rstrip("/")
JIRA_EMAIL   = os.environ["JIRA_EMAIL"].strip()
JIRA_TOKEN   = os.environ["JIRA_API_TOKEN"].strip()
NOTION_TOKEN = os.environ["NOTION_TOKEN"].strip()
NOTION_PAGE  = os.environ["NOTION_PAGE_ID"].strip().replace("-", "")

# ── Status mapping ────────────────────────────────────────────────────────────
STATUS_EMOJI = {
    "done":         "✅",
    "concluído":    "✅",
    "in progress":  "🔵",
    "em andamento": "🔵",
    "in review":    "🟡",
    "em testes":    "🟡",
    "validation":   "🟡",
    "to do":        "⚪",
    "backlog":      "⚪",
    "blocked":      "🔴",
    "bloqueado":    "🔴",
    "kickoff":      "⚪",
    "tarefas pendentes": "⚪",
}

SQUAD_MAP = {
    "marinho":  "Marinho / Isabella",
    "isabella": "Marinho / Isabella",
    "pamella":  "Pamella / Ingrid",
    "ingrid":   "Pamella / Ingrid",
    "vanessa":  "Vanessa / Ana",
    "ana":      "Vanessa / Ana",
    "giovanna": "Giovanna / Gallea",
    "gallea":   "Giovanna / Gallea",
    "fabricio": "Fabrício / Amanda",
    "fabrício": "Fabrício / Amanda",
    "amanda":   "Fabrício / Amanda",
}

def get_squad(assignee):
    if not assignee:
        return "Sem squad"
    a = assignee.lower()
    for key, squad in SQUAD_MAP.items():
        if key in a:
            return squad
    return assignee

def status_emoji(status):
    return STATUS_EMOJI.get(status.lower().strip(), "⚪")

# ── Jira ──────────────────────────────────────────────────────────────────────
def jira_request(path):
    credentials = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
    url = f"https://{JIRA_DOMAIN}/rest/api/3/{path}"
    print(f"  GET {url[:80]}...")
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code}: {e.reason} — {body[:300]}")
        raise

def fetch_issues():
    issues = []
    page_size = 50
    jql = urllib.parse.quote("project = PD ORDER BY status ASC, updated DESC")
    fields = "summary,status,assignee,duedate"
    next_token = None

    while True:
        path = f"search/jql?jql={jql}&maxResults={page_size}&fields={fields}"
        if next_token:
            path += f"&nextPageToken={urllib.parse.quote(next_token)}"
        data = jira_request(path)
        batch = data.get("issues", [])
        issues.extend(batch)
        print(f"  {len(issues)} issues carregadas")
        next_token = data.get("nextPageToken")
        if not next_token or data.get("isLast", True):
            break

    return issues

def group_by_squad(issues):
    squads = {}
    for issue in issues:
        fields   = issue.get("fields", {})
        summary  = fields.get("summary", "Sem título")
        status   = (fields.get("status") or {}).get("name", "Backlog")
        assignee = ((fields.get("assignee") or {}).get("displayName") or "")
        duedate  = fields.get("duedate") or "TBD"
        squad    = get_squad(assignee)
        emoji    = status_emoji(status)
        squads.setdefault(squad, []).append({
            "summary": summary,
            "status":  status,
            "emoji":   emoji,
            "duedate": duedate,
        })
    return squads

# ── Notion ────────────────────────────────────────────────────────────────────
def notion_request(method, path, body=None):
    url  = f"https://api.notion.com/v1/{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req  = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")
        print(f"  Notion HTTP {e.code}: {e.reason} — {body_txt[:300]}")
        raise

def clear_page_children(page_id):
    data = notion_request("GET", f"blocks/{page_id}/children")
    for block in data.get("results", []):
        notion_request("DELETE", f"blocks/{block['id']}")

def heading_block(content, level=2):
    htype = f"heading_{level}"
    return {
        "object": "block", "type": htype,
        htype: {"rich_text": [{"type": "text", "text": {"content": content}}]}
    }

def text_block(content):
    return {
        "object": "block", "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]}
    }

def divider_block():
    return {"object": "block", "type": "divider", "divider": {}}

def build_blocks(squads):
    today = datetime.now().strftime("%d/%m/%Y às %H:%M")
    blocks = [
        heading_block("📋 Roadmap Q2 — Status das Iniciativas", level=1),
        text_block(f"Última atualização: {today}   •   ✅ Concluído   🔵 Em andamento   🟡 Em testes/revisão   ⚪ Backlog   🔴 Bloqueado"),
        divider_block(),
    ]
    squad_order = [
        "Marinho / Isabella", "Pamella / Ingrid", "Vanessa / Ana",
        "Giovanna / Gallea", "Fabrício / Amanda", "Sem squad",
    ]
    for squad in squad_order:
        items = squads.get(squad)
        if not items:
            continue
        blocks.append(heading_block(f"Squad {squad}", level=2))
        for item in items:
            blocks.append(text_block(f"{item['emoji']} {item['summary']}  —  previsão: {item['duedate']}"))
        blocks.append(divider_block())
    return blocks

def append_blocks(page_id, blocks):
    for i in range(0, len(blocks), 100):
        notion_request("PATCH", f"blocks/{page_id}/children", {"children": blocks[i:i+100]})
    print(f"  {len(blocks)} blocos escritos.")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"Domínio Jira: {JIRA_DOMAIN}")
    print(f"Página Notion: {NOTION_PAGE}\n")

    print("1. Buscando issues no Jira...")
    issues = fetch_issues()
    print(f"   {len(issues)} issues encontradas.")

    print("2. Agrupando por squad...")
    squads = group_by_squad(issues)

    print("3. Limpando página do Notion...")
    clear_page_children(NOTION_PAGE)

    print("4. Escrevendo no Notion...")
    blocks = build_blocks(squads)
    append_blocks(NOTION_PAGE, blocks)

    print("\nSincronização concluída!")

if __name__ == "__main__":
    main()
