import os
import json
import urllib.request
import urllib.parse
import base64
from datetime import datetime

# ── Config (via GitHub Secrets) ───────────────────────────────────────────────
JIRA_DOMAIN   = os.environ["JIRA_DOMAIN"]        # stays.atlassian.net
JIRA_EMAIL    = os.environ["JIRA_EMAIL"]          # vanessa@stays.net
JIRA_TOKEN    = os.environ["JIRA_API_TOKEN"]      # token do Jira
JIRA_PROJECT  = os.environ.get("JIRA_PROJECT", "Product Team")

NOTION_TOKEN  = os.environ["NOTION_TOKEN"]        # token do Notion
NOTION_PAGE   = os.environ["NOTION_PAGE_ID"]      # 38826bb2d03f804a8378c5d4f1c23234

# ── Status mapping ────────────────────────────────────────────────────────────
STATUS_EMOJI = {
    "done":        "✅",
    "concluído":   "✅",
    "in progress": "🔵",
    "em andamento":"🔵",
    "in review":   "🟡",
    "em testes":   "🟡",
    "to do":       "⚪",
    "backlog":     "⚪",
    "blocked":     "🔴",
    "bloqueado":   "🔴",
}

SQUAD_MAP = {
    "marinho":   "Marinho / Isabella",
    "isabella":  "Marinho / Isabella",
    "pamella":   "Pamella / Ingrid",
    "ingrid":    "Pamella / Ingrid",
    "vanessa":   "Vanessa / Ana",
    "ana":       "Vanessa / Ana",
    "giovanna":  "Giovanna / Gallea",
    "gallea":    "Giovanna / Gallea",
    "fabrício":  "Fabrício / Amanda",
    "fabricio":  "Fabrício / Amanda",
    "amanda":    "Fabrício / Amanda",
}

def get_squad(assignee: str) -> str:
    if not assignee:
        return "Sem squad"
    a = assignee.lower()
    for key, squad in SQUAD_MAP.items():
        if key in a:
            return squad
    return assignee

def status_emoji(status: str) -> str:
    return STATUS_EMOJI.get(status.lower().strip(), "⚪")

# ── Jira ──────────────────────────────────────────────────────────────────────
def jira_request(path: str) -> dict:
    credentials = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
    url = f"https://{JIRA_DOMAIN}/rest/api/2/{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
        }
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def fetch_issues() -> list:
    """Busca todas as issues do projeto, paginando se necessário."""
    issues = []
    start = 0
    page_size = 50
    jql = urllib.parse.quote(f'project = "{JIRA_PROJECT}" ORDER BY status ASC, updated DESC')

    while True:
        data = jira_request(f"search?jql={jql}&startAt={start}&maxResults={page_size}&fields=summary,status,assignee,duedate,priority,issuetype")
        batch = data.get("issues", [])
        issues.extend(batch)
        if start + page_size >= data.get("total", 0):
            break
        start += page_size

    print(f"{len(issues)} issues encontradas no Jira.")
    return issues

def group_by_squad(issues: list) -> dict:
    squads = {}
    for issue in issues:
        fields    = issue.get("fields", {})
        summary   = fields.get("summary", "Sem título")
        status    = fields.get("status", {}).get("name", "Backlog")
        assignee  = (fields.get("assignee") or {}).get("displayName", "")
        duedate   = fields.get("duedate") or "TBD"
        squad     = get_squad(assignee)
        emoji     = status_emoji(status)

        if squad not in squads:
            squads[squad] = []
        squads[squad].append({
            "summary":  summary,
            "status":   status,
            "emoji":    emoji,
            "duedate":  duedate,
            "assignee": assignee,
        })
    return squads

# ── Notion ────────────────────────────────────────────────────────────────────
def notion_request(method: str, path: str, body: dict = None):
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
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def clear_page_children(page_id: str):
    """Remove todos os blocos filhos da página para reescrever do zero."""
    data = notion_request("GET", f"blocks/{page_id}/children")
    for block in data.get("results", []):
        notion_request("DELETE", f"blocks/{block['id']}")

def text_block(content: str, bold=False) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": content}, "annotations": {"bold": bold}}]
        }
    }

def heading_block(content: str, level=2) -> dict:
    htype = f"heading_{level}"
    return {
        "object": "block",
        "type": htype,
        htype: {
            "rich_text": [{"type": "text", "text": {"content": content}}]
        }
    }

def divider_block() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}

def build_notion_blocks(squads: dict) -> list:
    today = datetime.now().strftime("%d/%m/%Y às %H:%M")
    blocks = []

    # Cabeçalho
    blocks.append(heading_block("📋 Roadmap Q2 — Status das Iniciativas", level=1))
    blocks.append(text_block(f"Última atualização: {today}   •   ✅ Concluído   🔵 Em andamento   🟡 Em testes   ⚪ Backlog   🔴 Bloqueado"))
    blocks.append(divider_block())

    squad_order = [
        "Marinho / Isabella",
        "Pamella / Ingrid",
        "Vanessa / Ana",
        "Giovanna / Gallea",
        "Fabrício / Amanda",
        "Sem squad",
    ]

    for squad in squad_order:
        issues = squads.get(squad)
        if not issues:
            continue

        blocks.append(heading_block(f"Squad {squad}", level=2))

        for issue in issues:
            line = f"{issue['emoji']} {issue['summary']}  —  previsão: {issue['duedate']}"
            blocks.append(text_block(line))

        blocks.append(divider_block())

    return blocks

def append_blocks_to_page(page_id: str, blocks: list):
    """Notion limita 100 blocos por request — envia em lotes."""
    chunk_size = 100
    for i in range(0, len(blocks), chunk_size):
        chunk = blocks[i:i + chunk_size]
        notion_request("PATCH", f"blocks/{page_id}/children", {"children": chunk})
    print(f"{len(blocks)} blocos escritos no Notion.")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Buscando issues no Jira...")
    issues = fetch_issues()

    print("Agrupando por squad...")
    squads = group_by_squad(issues)

    print("Limpando página do Notion...")
    clear_page_children(NOTION_PAGE)

    print("Escrevendo conteúdo no Notion...")
    blocks = build_notion_blocks(squads)
    append_blocks_to_page(NOTION_PAGE, blocks)

    print("Sincronização concluída!")

if __name__ == "__main__":
    main()
