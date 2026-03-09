"""
Smart Action Engine for N.A.T. AI Assistant
───────────────────────────────────────────
Intercepts every user message BEFORE it reaches the normal chat flow.
Uses Groq to classify the intent into a structured JSON command,
then routes it to the correct service (terminal, browser, file system, etc.).

Supported action types:
  open_web        → Open a URL in the browser
  web_search      → Search the web (Google/YouTube/GitHub/etc.)
  run_terminal    → Execute a shell command
  create_folder   → Create a directory
  create_file     → Create a file (optionally with content)
  open_folder     → Open a folder in the OS file explorer
  open_file       → Open a file with the default app
  open_app        → Launch an installed application
  list_directory  → List contents of a directory
  chat            → Normal conversation (pass through to LLM)
"""

import json
import re
from app.services.groq_service import groq_service


_SYSTEM_PROMPT = '''You are a strict JSON command router for a local AI assistant called Natasha.
Analyze the user message and return ONLY raw JSON (no markdown, no explanation).

Supported actions:

1. open_web      → open a specific website
   {"action": "open_web", "target": "https://www.youtube.com"}

2. web_search    → search the web for something
   {"action": "web_search", "query": "best Python tutorials", "engine": "google"}
   engine options: google, youtube, github, bing

3. run_terminal  → run a shell/terminal command
   {"action": "run_terminal", "command": "pip install requests", "cwd": null}

4. create_folder → create a new folder/directory
   {"action": "create_folder", "path": "C:/Users/jishu/Projects/NewApp"}

5. create_file   → create a new file
   {"action": "create_file", "path": "C:/Users/jishu/notes.txt", "content": ""}

6. open_folder   → open folder in file explorer
   {"action": "open_folder", "path": "C:/Users/jishu/Documents"}

7. open_file     → open a file with default app
   {"action": "open_file", "path": "C:/Users/jishu/report.pdf"}

8. open_app      → launch an installed application
   {"action": "open_app", "app": "Notepad"}

9. list_directory → list contents of a folder
   {"action": "list_directory", "path": "C:/Users/jishu/Projects"}

10. chat          → everything else (questions, AI tasks, conversations)
    {"action": "chat"}

RULES:
- "open google" → open_web https://www.google.com
- "search X on youtube" → web_search engine=youtube
- "create folder called X" → create_folder
- "run this: X" → run_terminal
- "open my documents" → open_folder with Documents path
- Return ONLY raw JSON object. No markdown. No explanation.
'''


class SmartActionEngine:
    def __init__(self):
        self.local_mappings = {
            "Doctor Drift": "C:\\Users\\jishu\\DoctorDrift",
            "Protein Zone": "C:\\Users\\jishu\\ProteinZone",
        }

    def _classify_intent(self, user_message: str) -> dict:
        """Ask Groq to classify intent. Returns parsed dict or None."""
        try:
            print(f"\n[ActionEngine] Classifying: '{user_message}'")
            response = groq_service.chat(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=_SYSTEM_PROMPT
            )
            print(f"[ActionEngine] Raw LLM: {response}")

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                print(f"[ActionEngine] Parsed: {data}")
                return data
        except Exception as e:
            print(f"[ActionEngine] Classification error: {e}")
        return None

    def _resolve_local_path(self, target: str) -> str:
        """Resolve user-defined local app names to real paths."""
        for key, path in self.local_mappings.items():
            if key.lower() in target.lower() or target.lower() in key.lower():
                return path
        return target

    def evaluate_and_execute(self, user_message: str):
        """Main entry point called by the streaming generator."""
        data = self._classify_intent(user_message)
        if not data:
            return None

        action = data.get("action", "chat")
        if action == "chat":
            return None

        from app.services.terminal_browser_service import terminal_service, browser_service

        if action == "open_web":
            url = data.get("target", "")
            resolved = self._resolve_local_path(url)
            if resolved != url:
                result = terminal_service.open_app(resolved)
                return f"Launching **{resolved}**..." if result["success"] else f"Failed: {result['message']}"
            result = browser_service.open_url_simple(url)
            return f"Opening **{url}** in your browser..." if result["success"] else f"Failed to open browser: {result['message']}"

        elif action == "web_search":
            query = data.get("query", user_message)
            engine = data.get("engine", "google")
            result = browser_service.open_search(query, engine)
            return f"Searching **\"{query}\"** on {engine.capitalize()}..." if result["success"] else f"Search failed: {result['message']}"

        elif action == "run_terminal":
            command = data.get("command", "")
            cwd = data.get("cwd") or None
            if not command:
                return "No command specified."
            result = terminal_service.run(command, cwd=cwd)
            if result["success"]:
                out = result["output"]
                response = f"Command executed: `{command}`\n\n"
                if out and out != "(no output)":
                    if len(out) > 1000:
                        out = out[:1000] + "\n... (output truncated)"
                    response += f"```\n{out}\n```"
                else:
                    response += "*(Completed with no output)*"
                return response
            else:
                err = result.get("error", "Unknown error")
                return f"Command failed: `{command}`\n\n```\n{err}\n```"

        elif action == "create_folder":
            path = data.get("path", "")
            result = terminal_service.create_folder(path)
            return f"Folder created: `{result['path']}`" if result["success"] else f"Failed to create folder: {result['message']}"

        elif action == "create_file":
            path = data.get("path", "")
            content = data.get("content", "")
            result = terminal_service.create_file(path, content)
            return f"File created: `{result['path']}`" if result["success"] else f"Failed to create file: {result['message']}"

        elif action == "open_folder":
            path = data.get("path", "")
            result = terminal_service.open_path(path)
            return f"Opening folder: `{result['path']}`..." if result["success"] else f"Failed: {result['message']}"

        elif action == "open_file":
            path = data.get("path", "")
            result = terminal_service.open_path(path)
            return f"Opening file: `{result['path']}`..." if result["success"] else f"Failed: {result['message']}"

        elif action == "open_app":
            app = data.get("app", "")
            resolved = self._resolve_local_path(app)
            if resolved != app:
                result = terminal_service.open_path(resolved)
            else:
                result = terminal_service.open_app(app)
            return f"Launching **{app}**..." if result["success"] else f"Failed to launch {app}: {result['message']}"

        elif action == "list_directory":
            path = data.get("path", ".")
            result = terminal_service.list_directory(path)
            if not result["success"]:
                return f"Cannot list directory: {result['message']}"

            items = result["items"]
            output = f"**{result['path']}** — {result['count']} items\n\n"
            folders = [i for i in items if i["type"] == "folder"]
            files   = [i for i in items if i["type"] == "file"]

            if folders:
                output += "**Folders:**\n"
                for f in folders[:20]:
                    output += f"  {f['name']}/\n"
            if files:
                output += "\n**Files:**\n"
                for f in files[:20]:
                    size = f"{f['size']:,} B" if f["size"] is not None else ""
                    output += f"  {f['name']}  {size}\n"
            if result["count"] > 40:
                output += f"\n...and {result['count'] - 40} more items"
            return output

        return None


action_engine = SmartActionEngine()
