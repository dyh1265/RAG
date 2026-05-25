# Security Policy

## Reporting a vulnerability

If you discover a security issue, **please do not open a public GitHub issue**. Instead, report it privately:

- Open a [GitHub Security Advisory](../../security/advisories/new) on this repository, or
- Email the maintainer (see commit history for contact).

Please include:
- A description of the issue and its impact
- Steps to reproduce
- Affected version / commit SHA
- Any suggested mitigation

You should receive an acknowledgment within a few days. We will work with you to validate, fix, and disclose responsibly.

## Scope

This project ships:
- A Python multimodal RAG pipeline (FastAPI service, Celery workers, CLI)
- A React + nginx web frontend
- Docker compose stacks for local and demo deployment

In-scope examples: auth bypass on the API, prompt-injection paths that exfiltrate ingested documents, container escapes in the provided Dockerfiles, RCE via crafted PDFs, dependency CVEs we can reasonably update.

Out of scope: issues in upstream dependencies that are already patched, denial-of-service from running the demo on a public IP without a reverse proxy, social-engineering attacks against the demo URL.

## Secrets hygiene

This repo never tracks `.env`. **Never commit API keys.** Before pushing:

```bash
# Confirm .env is ignored
git check-ignore -v .env

# Scan staged content for obvious secrets
git diff --cached | grep -E "sk-(proj-|live-)?[A-Za-z0-9_-]{20,}"
```

If you ever do accidentally commit a key, **rotate it immediately** at the provider (OpenAI, Anthropic, etc.) before worrying about rewriting history.
