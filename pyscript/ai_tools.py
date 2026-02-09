import subprocess
import json
import urllib.request
import urllib.error
import os


@service(supports_response="optional")
def ai_execute_ha_service(list=None):
    """Execute HA services with null values stripped from service_data."""
    if not list:
        return {"error": "No service calls provided"}
    results = []
    for item in list:
        domain = item.get("domain", "")
        svc = item.get("service", "")
        data = item.get("service_data", {})
        # Strip None/null values to prevent HA errors
        clean_data = {k: v for k, v in data.items() if v is not None}
        try:
            service.call(domain, svc, **clean_data)
            results.append({"domain": domain, "service": svc, "success": True})
        except Exception as e:
            results.append({"domain": domain, "service": svc, "success": False, "error": str(e)})
    return {"results": results}


@service(supports_response="optional")
def ai_execute_command(command=None, timeout=30):
    """Execute a shell command on the Home Assistant server and return the output."""
    if not command:
        return {"error": "No command provided", "returncode": -1}
    try:
        result = task.executor(
            subprocess.run,
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=int(timeout or 30),
        )
        return {
            "stdout": result.stdout[-4000:] if result.stdout else "",
            "stderr": result.stderr[-1000:] if result.stderr else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout}s", "returncode": -1}
    except Exception as e:
        return {"error": str(e), "returncode": -1}


@service(supports_response="optional")
def ai_http_request(url=None, method="GET", headers=None, body=None, timeout=15):
    """Make an HTTP request and return the response. Headers should be a JSON string like '{"Key": "Value"}'."""
    if not url:
        return {"error": "No URL provided"}
    try:
        req = urllib.request.Request(url, method=method.upper())
        if headers:
            if isinstance(headers, str):
                headers = json.loads(headers)
            for key, value in headers.items():
                req.add_header(key, value)
        if body:
            if isinstance(body, dict):
                body = json.dumps(body)
            req.data = body.encode("utf-8")
            if "Content-Type" not in (headers or {}):
                req.add_header("Content-Type", "application/json")

        def do_request():
            with urllib.request.urlopen(req, timeout=int(timeout or 15)) as resp:
                return {
                    "status": resp.status,
                    "body": resp.read().decode("utf-8", errors="replace")[:5000],
                }

        return task.executor(do_request)
    except urllib.error.HTTPError as e:
        return {
            "status": e.code,
            "error": str(e.reason),
            "body": e.read().decode("utf-8", errors="replace")[:2000],
        }
    except Exception as e:
        return {"error": str(e)}


@service(supports_response="optional")
def ai_write_file(path=None, content=None, make_executable=False):
    """Write content to a file. Set make_executable=true for shell scripts."""
    if not path or content is None:
        return {"error": "Both path and content are required"}
    try:
        allowed_dirs = ["/config/scripts/", "/config/pyscript/", "/config/packages/", "/tmp/"]
        if not any(path.startswith(d) for d in allowed_dirs):
            return {"error": f"Writing only allowed in: {', '.join(allowed_dirs)}"}

        def do_write():
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            if make_executable:
                os.chmod(path, 0o755)
            return {"success": True, "path": path, "bytes_written": len(content)}

        return task.executor(do_write)
    except Exception as e:
        return {"error": str(e)}


@service(supports_response="optional")
def ai_read_file(path=None):
    """Read content from a file."""
    if not path:
        return {"error": "Path is required"}
    try:

        def do_read():
            with open(path, "r") as f:
                content = f.read()
            return {"content": content[:8000], "size": len(content)}

        return task.executor(do_read)
    except Exception as e:
        return {"error": str(e)}


@service(supports_response="optional")
def ai_delete_automation(automation_id=None):
    """Delete an automation by its config ID. From inside an automation, pass {{ this.attributes.id }}."""
    if not automation_id:
        return {"error": "automation_id is required (the config ID, not entity_id)"}
    try:
        token = open("/config/secrets.yaml").read()
        token = [l.split(":", 1)[1].strip().strip('"') for l in token.splitlines() if l.startswith("ha_token:")][0]
        cmd = f'curl -s -X DELETE -H "Authorization: Bearer {token}" http://localhost:8123/api/config/automation/config/{automation_id}'
        result = task.executor(
            subprocess.run, cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        return {"deleted": result.returncode == 0, "automation_id": automation_id, "output": result.stdout}
    except Exception as e:
        return {"error": str(e)}


@service(supports_response="optional")
def ai_youtube_search(query=None, max_results=5):
    """Search YouTube and return video titles, IDs, and URLs."""
    if not query:
        return {"error": "No search query provided"}
    try:
        result = task.executor(
            subprocess.run,
            ["python3", "/config/scripts/youtube_search.py", str(query), str(int(max_results))],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return {"error": result.stderr[:500] or "YouTube search failed"}
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e)}


@service(supports_response="optional")
def ai_manage_cron(action="list", schedule=None, command=None, comment=None):
    """Manage cron jobs. Actions: list, add, remove. Schedule format: '*/5 * * * *'. Comment is used as ID for removal."""
    try:
        if action == "list":
            result = task.executor(
                subprocess.run,
                "crontab -l 2>/dev/null || echo 'no crontab'",
                shell=True,
                capture_output=True,
                text=True,
            )
            return {"crontab": result.stdout}

        elif action == "add":
            if not schedule or not command:
                return {"error": "schedule and command are required for 'add'"}
            tag = comment or command[:30]
            line = f"{schedule} {command} # {tag}"
            cmd = f'(crontab -l 2>/dev/null | grep -v "# {tag}"; echo "{line}") | crontab -'
            result = task.executor(
                subprocess.run, cmd, shell=True, capture_output=True, text=True
            )
            return {
                "success": result.returncode == 0,
                "added": line,
                "stderr": result.stderr,
            }

        elif action == "remove":
            if not comment:
                return {"error": "comment (tag) is required to identify the job to remove"}
            cmd = f'crontab -l 2>/dev/null | grep -v "# {comment}" | crontab -'
            result = task.executor(
                subprocess.run, cmd, shell=True, capture_output=True, text=True
            )
            return {"success": result.returncode == 0, "removed_tag": comment}

        else:
            return {"error": f"Unknown action: {action}. Use list, add, or remove."}
    except Exception as e:
        return {"error": str(e)}
