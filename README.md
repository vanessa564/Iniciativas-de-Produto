# Jira → Notion Sync 🤖

Sincroniza automaticamente as issues do Jira com uma página pública do Notion, agrupadas por squad.

---

## GitHub Secrets necessários

| Secret | Valor |
|---|---|
| `JIRA_DOMAIN` | `stays.atlassian.net` |
| `JIRA_EMAIL` | `vanessa@stays.net` |
| `JIRA_API_TOKEN` | Token gerado em id.atlassian.com |
| `NOTION_TOKEN` | Token gerado em notion.so/my-integrations |
| `NOTION_PAGE_ID` | `38826bb2d03f804a8378c5d4f1c23234` |

---

## Como adicionar os secrets no GitHub

1. Abra o repositório no GitHub
2. Vá em **Settings → Secrets and variables → Actions**
3. Clique em **New repository secret** para cada linha da tabela acima

---

## Mudar o projeto do Jira

No arquivo `.github/workflows/jira_notion.yml`, edite a linha:
```yaml
JIRA_PROJECT: "Product Team"
```

---

## Mudar o agendamento

No mesmo arquivo, edite a linha:
```yaml
- cron: "0 12 * * 1,3,5"  # seg/qua/sex às 9h (Brasília)
```

---

## Tornar a página do Notion pública

1. Abra a página no Notion
2. Clique em **Share** no canto superior direito
3. Ative **Share to web**
4. Copie o link e distribua para os stakeholders
