# Sahaay Permissions, Consent, and Privacy Architecture

## 1. Core Principles
1. **Default-Deny / Fail-Closed**: Any unpermitted action, unmapped scope, or unverified network call is denied by default.
2. **Deterministic Action Gate**: Models propose; deterministic application logic authorizes. Models cannot bypass authorization.
3. **Decoupled Consent**: Policy and user consent decisions are separate from model prompts and system instructions.
4. **Local-Only Guarantee**: In Local-Only Mode, the Privacy Gateway strictly blocks external transmission.
5. **No Shell Execution**: General-purpose shells (PowerShell, Command Prompt, bash) are never exposed to model output or public APIs.

---

## 2. Consent Grant Lifecycle

```
[User Consent Dialog]
        │
        ▼ (User Grants Consent for Specific Scope)
[POST /api/v1/sessions/{id}/grants]
        │
        ▼
[ConsentGrant Created] ──► Validated by ActionGate on every ProposeAction
        │
        ▼ (User clicks Revoke / Expiration occurs)
[DELETE /api/v1/sources/{id}] / [Grant Marked isRevoked=true]
        │
        ▼
[Subsequent Actions Fail Closed Immediately]
```

### Supported Scopes
- `read_file:<path>`: Grants read-only access to a specific file or folder.
- `search_files:<dir>`: Grants search access within an authorized directory.
- `get_active_tab_info`: Grants permission to read title and URL of the active browser tab.
- `get_tab_content`: Grants permission to extract sanitized text content from authorized tabs.
- `navigate_browser_tab`: Grants permission to navigate active tab to authorized URLs.
- `click_browser_element`: Grants permission to interact with authorized web elements.
- `focus_window:<name>`: Grants permission to bring an authorized window to the foreground.
- `click_desktop_control:<id>`: Grants permission to click an authorized UI Automation control.

---

## 3. Data Classification Matrix

| Classification | Definition | External Transmission Permitted? |
| :--- | :--- | :--- |
| `PUBLIC` | Open public information, public webpage contents | Only with explicit user consent |
| `INTERNAL` | General desktop state, non-sensitive notes, file names | Only with explicit user consent |
| `SENSITIVE_PII` | Email addresses, phone numbers, personal identifiers | Redacted or blocked; requires high-trust grant |
| `CREDENTIAL` | API keys, passwords, bearer tokens, private keys | **NEVER** (Permanently blocked from outbound transmission) |
| `HIGHLY_RESTRICTED` | Protected system credentials or financial documents | **NEVER** |
