#!/usr/bin/env python3
"""Codex Auto Iterations Loop – Propose → Apply → Test → Evaluate → Revise.

Dieses Skript orchestriert einen vollständig konfigurierbaren Auto-Iterations-
Prozess für Code- oder Content-Repositories. Es lädt eine YAML-Konfiguration,
ruft ein Sprachmodell zur Patch-Erzeugung auf, führt Tests/Checks aus und be-
wertet die Ergebnisse. Die Architektur ist absichtlich modular gehalten, damit
du die Modell-Anbindung einfach austauschen kannst.

Neu in dieser Version:

* Unterstützung für echte API-Adapter (OpenAI, Ollama) neben dem Mock-Modus.
* Robuste JSON-Extraktion aus LLM-Antworten (auch bei Code-Fences oder Prosa).
* Konfigurierbare Adapter-Wahl über YAML oder Umgebungsvariable.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:  # pragma: no cover - optional helper
    from github_sync import GitHubTarget, upload as github_upload
except Exception:  # pragma: no cover - github_sync is optional
    GitHubTarget = None  # type: ignore[assignment]
    github_upload = None  # type: ignore[assignment]

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("PyYAML wird benötigt. Installiere es mit 'pip install pyyaml'.") from exc


# ---------------------------------------------------------------------------
# Fehlerklassen
# ---------------------------------------------------------------------------


class AdapterError(RuntimeError):
    """Wird ausgelöst, wenn der hinterlegte LLM-Adapter fehlschlägt."""


# ---------------------------------------------------------------------------
# Hilfsfunktionen für Datei- und Zeitoperationen
# ---------------------------------------------------------------------------


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(content)


def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return handle.read()


def utc_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Datenstrukturen
# ---------------------------------------------------------------------------


@dataclass
class Patch:
    file: str
    content: str


@dataclass
class Proposal:
    plan: str = ""
    patches: List[Patch] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Proposal":
        raw_patches = data.get("patches", []) or []
        patches = [Patch(file=p["file"], content=p.get("content", "")) for p in raw_patches]
        return cls(
            plan=data.get("plan", ""),
            patches=patches,
            tests=list(data.get("tests", []) or []),
            notes=data.get("notes", ""),
        )


@dataclass
class CommandResult:
    cmd: str
    code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.code == 0


@dataclass
class PatchReport:
    file: str
    changed: bool
    diff: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class Evaluation:
    decision: str
    reason: str
    next_hints: List[str]


# ---------------------------------------------------------------------------
# Adapter-Helfer
# ---------------------------------------------------------------------------


def ensure_json_dict(payload: str) -> Dict[str, Any]:
    """Extrahiert ein JSON-Objekt aus dem LLM-Output."""

    text = payload.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```$", "", text.strip())
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                raise AdapterError(f"Antwort enthält kein gültiges JSON: {text}") from exc
        raise AdapterError(f"Antwort enthält kein JSON-Objekt: {text}")


def build_user_message(action: str, user_prompt: str, context: Dict[str, Any]) -> str:
    if action != "evaluate":
        return user_prompt

    merged = {
        "instruction": user_prompt,
        "artifacts": context.get("artifacts", {}),
        "logs": context.get("logs", {}),
    }
    return json.dumps(merged, ensure_ascii=False)


def call_adapter(
    *,
    action: str,
    adapter: str,
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    adapter = adapter.lower()
    ctx = context or {}

    if adapter == "mock":
        if action == "complete":
            return {
                "plan": "Mock-Lauf: keine Änderungen vorgenommen.",
                "patches": [],
                "tests": [],
                "notes": "Adapter=mock – bitte API integrieren.",
            }
        return {
            "decision": "success" if all(log.get("ok", True) for log in ctx.get("logs", {}).get("exec", [])) else "continue",
            "reason": "Mock-Adapter – benutze echte API für präzisere Bewertung.",
            "next_hints": [
                "Prüfe die Kommando-Logs.",
                "Minimiere Patch-Größe und erhalte Fokus auf das Ziel.",
                "Integriere dein LLM über llm_complete/llm_evaluate.",
            ],
        }

    if adapter == "openai":
        return call_openai(
            action=action,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            context=ctx,
        )

    if adapter == "ollama":
        return call_ollama(
            action=action,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            context=ctx,
        )

    raise AdapterError(f"Unbekannter Adapter '{adapter}'. Unterstützt: mock, openai, ollama.")


def call_openai(
    *,
    action: str,
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise AdapterError("Das 'requests'-Paket wird für den OpenAI-Adapter benötigt.") from exc

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise AdapterError("OPENAI_API_KEY ist nicht gesetzt.")

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/chat/completions"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_user_message(action, user_prompt, context)},
    ]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise AdapterError(f"OpenAI-Anfrage fehlgeschlagen: {exc}") from exc
    except ValueError as exc:  # pragma: no cover
        raise AdapterError("OpenAI lieferte keine gültige JSON-Antwort.") from exc

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise AdapterError(f"Unerwartetes OpenAI-Antwortformat: {data}") from exc

    return ensure_json_dict(text)


def call_ollama(
    *,
    action: str,
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise AdapterError("Das 'requests'-Paket wird für den Ollama-Adapter benötigt.") from exc

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    url = f"{base_url}/api/generate"

    prompt = build_user_message(action, user_prompt, context)
    full_prompt = f"{system_prompt.strip()}\n\n{prompt.strip()}"

    payload = {
        "model": model,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise AdapterError(f"Ollama-Anfrage fehlgeschlagen: {exc}") from exc
    except ValueError as exc:  # pragma: no cover
        raise AdapterError("Ollama lieferte keine gültige JSON-Antwort.") from exc

    text = data.get("response", "").strip()
    if not text:
        raise AdapterError(f"Ollama-Antwort leer: {data}")

    return ensure_json_dict(text)


# ---------------------------------------------------------------------------
# Modell-Adaptionen
# ---------------------------------------------------------------------------


def llm_complete(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    adapter: str,
) -> Proposal:
    raw = call_adapter(
        action="complete",
        adapter=adapter,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return Proposal.from_dict(raw)


def llm_evaluate(
    system_prompt: str,
    user_prompt: str,
    *,
    artifacts: Dict[str, Any],
    logs: Dict[str, Any],
    model: str,
    temperature: float,
    max_tokens: int,
    adapter: str,
) -> Evaluation:
    raw = call_adapter(
        action="evaluate",
        adapter=adapter,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        context={"artifacts": artifacts, "logs": logs},
    )

    command_logs: List[Dict[str, Any]] = logs.get("exec", [])
    decision = raw.get("decision") or ("success" if all(log.get("ok", True) for log in command_logs) else "continue")
    reason = raw.get("reason") or "Automatische Heuristik basierend auf Kommando-Resultaten."
    hints = list(raw.get("next_hints", []) or [])
    if not hints:
        hints = [
            "Prüfe die Kommando-Logs.",
            "Minimiere Patch-Größe und erhalte Fokus auf das Ziel.",
            "Integriere dein LLM über llm_complete/llm_evaluate.",
        ]
    return Evaluation(decision=decision, reason=reason, next_hints=hints)


# ---------------------------------------------------------------------------
# Ausführungshilfen
# ---------------------------------------------------------------------------


def run_cmd(cmd: str, *, cwd: Path) -> CommandResult:
    try:
        process = subprocess.run(
            cmd,
            cwd=str(cwd),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return CommandResult(cmd=cmd, code=process.returncode, stdout=process.stdout, stderr=process.stderr)
    except Exception as exc:  # pragma: no cover
        return CommandResult(cmd=cmd, code=-999, stdout="", stderr=str(exc))


def unified_diff(old: str, new: str, *, rel_path: str) -> str:
    import difflib

    return "\n".join(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
            lineterm="",
        )
    )


def apply_patches(root: Path, patches: Iterable[Patch], *, dry_run: bool) -> List[PatchReport]:
    reports: List[PatchReport] = []
    for patch in patches:
        target = root / patch.file
        original = target.exists() and read_text(target) or ""
        if original == patch.content:
            reports.append(PatchReport(file=patch.file, changed=False, reason="no-op"))
            continue
        diff = unified_diff(original, patch.content, rel_path=patch.file)
        if not dry_run:
            write_text(target, patch.content)
        reports.append(PatchReport(file=patch.file, changed=True, diff=diff))
    return reports


def success_from_rules(root: Path, logs: Dict[str, Any], rules: Dict[str, Any]) -> tuple[bool, str]:
    if rules.get("all_commands_zero"):
        if any(not entry.get("ok", False) for entry in logs.get("exec", [])):
            return False, "Mindestens ein Kommando meldete einen Fehler."

    for requirement in rules.get("must_contain", []) or []:
        file_path = root / requirement.get("file", "")
        expected = requirement.get("contains", "")
        if not file_path.exists():
            return False, f"Datei fehlt: {file_path}"
        if expected not in read_text(file_path):
            return False, f"'{expected}' nicht in {file_path} gefunden."

    for rule in rules.get("forbidden", []) or []:
        file_path = root / rule.get("file", "")
        needle = rule.get("contains", "")
        if file_path.exists() and needle in read_text(file_path):
            return False, f"Verbotenes Pattern '{needle}' in {file_path} gefunden."

    return True, "Alle Erfolgsregeln erfüllt."


# ---------------------------------------------------------------------------
# GitHub-Sync
# ---------------------------------------------------------------------------


def maybe_sync_to_github(
    config: Dict[str, Any],
    iteration_label: str,
    log_dir: Path,
    *,
    extra_paths: Optional[List[str]] = None,
    use_config_paths: bool = True,
) -> None:
    sync_cfg = config.get("github_sync") or {}
    if not sync_cfg or not sync_cfg.get("enabled"):
        return

    if github_upload is None or GitHubTarget is None:
        print("GitHub-Sync aktiviert, aber github_sync.py konnte nicht importiert werden – übersprungen.")
        return

    repository = sync_cfg.get("repository")
    if not repository or "/" not in repository:
        print("GitHub-Sync: 'repository' muss im Format owner/name angegeben werden – übersprungen.")
        return

    branch = sync_cfg.get("branch", "main")
    remote_base = (sync_cfg.get("remote_base") or "").strip("/")
    message_template = sync_cfg.get("message_template", "Codex iteration {iter_label}")

    iteration_number = iteration_label.split("_", 1)[-1]
    placeholders = {
        "iter_label": iteration_label,
        "iteration": iteration_label,
        "iteration_id": iteration_label,
        "iteration_number": iteration_number,
        "log_dir": str(log_dir),
    }

    try:
        message = message_template.format(**placeholders)
    except KeyError as exc:
        print(f"GitHub-Sync: Unbekannter Platzhalter in message_template: {exc}")
        message = f"Codex iteration {iteration_label}"

    path_templates: List[str] = []
    if use_config_paths:
        path_templates.extend(sync_cfg.get("paths") or [])
    if extra_paths:
        path_templates.extend(extra_paths)

    if not path_templates:
        path_templates.append("{log_dir}/{iter_label}.json")

    resolved_paths: List[Path] = []
    cwd = Path.cwd()
    for template in path_templates:
        try:
            rendered = template.format(**placeholders)
        except KeyError as exc:
            print(f"GitHub-Sync: Unbekannter Platzhalter {exc} in Pfad '{template}' – übersprungen.")
            continue
        candidate = Path(rendered).expanduser()
        if not candidate.is_absolute():
            candidate = (cwd / candidate).resolve()
        if not candidate.exists():
            print(f"GitHub-Sync: {candidate} existiert nicht – übersprungen.")
            continue
        resolved_paths.append(candidate)

    if not resolved_paths:
        print("GitHub-Sync: Keine vorhandenen Dateien zum Hochladen.")
        return

    owner, repo = repository.split("/", 1)
    target = GitHubTarget(owner=owner, repo=repo, branch=branch)

    for path in resolved_paths:
        try:
            github_upload(target, path, remote_base, message)
            destination = f"{repository}/{remote_base}" if remote_base else f"{repository}/"
            print(f"GitHub-Sync: {path} → {destination}")
        except Exception as exc:  # pragma: no cover - Netzwerkabhängig
            print(f"GitHub-Sync: Upload für {path} fehlgeschlagen: {exc}")


# ---------------------------------------------------------------------------
# Haupt-Loop
# ---------------------------------------------------------------------------


def main(argv: List[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("Usage: python codex_auto_loop.py CONFIG.yaml")
        return 1

    config_path = Path(argv[0]).expanduser()
    if not config_path.exists():
        print(f"Konfigurationsdatei nicht gefunden: {config_path}")
        return 1

    config = load_yaml(config_path)

    workdir = Path(config.get("workdir", ".")).expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    log_dir = Path(config.get("log_dir", ".codex_logs")).expanduser().resolve()
    log_dir.mkdir(parents=True, exist_ok=True)

    max_iters = int(config.get("max_iters", 10))
    dry_run = bool(config.get("dry_run", False))
    sleep_seconds = float(config.get("sleep_between_iters_sec", 0.0))

    goal = config.get("goal", "Improve the project to pass tests.")
    constraints = config.get("constraints", []) or []
    commands = config.get("commands", []) or []
    rules = config.get("success_rules", {"all_commands_zero": True})

    system_prompt = config.get(
        "system_prompt",
        "You are an autonomous code-generation agent. Produce safe, minimal patches in JSON.",
    )

    adapter_name = str(config.get("adapter", "env") or "env").strip().lower()
    if adapter_name in {"env", ""}:
        adapter_name = os.environ.get("CODEX_LOOP_ADAPTER", "mock").lower()
    else:
        os.environ["CODEX_LOOP_ADAPTER"] = adapter_name

    model_name = config.get("model", "gpt-code")
    temperature = float(config.get("temperature", 0.2))
    max_tokens = int(config.get("max_tokens", 1500))

    history: List[Dict[str, Any]] = []
    last_iteration_label: Optional[str] = None

    for iteration in range(1, max_iters + 1):
        iteration_id = f"{iteration:03d}"
        print(f"\n=== Iteration {iteration_id} @ {utc_now()} (Adapter: {adapter_name}) ===")

        sampled_files: List[Dict[str, Any]] = []
        for index, path in enumerate(sorted(workdir.rglob("*"))):
            if path.is_file() and path.stat().st_size <= 200_000:
                sampled_files.append({"file": str(path.relative_to(workdir))})
            if index >= 200:
                break

        user_payload = {
            "goal": goal,
            "constraints": constraints,
            "iteration": iteration,
            "files_sample": [item["file"] for item in sampled_files[:25]],
            "last_notes": history[-1]["evaluation"]["next_hints"] if history else [],
        }
        user_prompt = json.dumps(user_payload, ensure_ascii=False)

        try:
            proposal = llm_complete(
                system_prompt,
                user_prompt,
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                adapter=adapter_name,
            )
        except AdapterError as exc:
            print(f"Adapter-Fehler während 'complete': {exc}")
            return 2

        patch_report = apply_patches(workdir, proposal.patches, dry_run=dry_run)

        exec_logs: List[Dict[str, Any]] = []
        for cmd in list(proposal.tests) + list(commands):
            result = run_cmd(cmd, cwd=workdir)
            exec_logs.append({
                "cmd": result.cmd,
                "code": result.code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "ok": result.ok,
            })
            print(f"$ {result.cmd} -> code={result.code}")
            if result.stdout.strip():
                print(result.stdout)
            if result.stderr.strip():
                print(result.stderr)

        rules_ok, rules_msg = success_from_rules(workdir, {"exec": exec_logs}, rules)

        eval_payload = {
            "goal": goal,
            "constraints": constraints,
            "iteration": iteration,
        }

        try:
            evaluation = llm_evaluate(
                system_prompt,
                json.dumps(eval_payload, ensure_ascii=False),
                artifacts={
                    "plan": proposal.plan,
                    "patches": [patch.__dict__ for patch in proposal.patches],
                    "notes": proposal.notes,
                },
                logs={"exec": exec_logs},
                model=model_name,
                temperature=max(temperature / 2, 0.0),
                max_tokens=max(256, max_tokens // 2 if max_tokens > 0 else 256),
                adapter=adapter_name,
            )
        except AdapterError as exc:
            print(f"Adapter-Fehler während 'evaluate': {exc}")
            return 3

        snapshot = {
            "iteration": iteration,
            "time": utc_now(),
            "proposal": {
                "plan": proposal.plan,
                "notes": proposal.notes,
                "tests": proposal.tests,
                "patches": [patch.__dict__ for patch in proposal.patches],
            },
            "patch_report": [report.__dict__ for report in patch_report],
            "exec": exec_logs,
            "rule_check": {"ok": rules_ok, "msg": rules_msg},
            "evaluation": {
                "decision": evaluation.decision,
                "reason": evaluation.reason,
                "next_hints": evaluation.next_hints,
            },
        }
        history.append(snapshot)

        iter_label = f"iter_{iteration_id}"
        iter_log_path = log_dir / f"{iter_label}.json"
        write_text(iter_log_path, json.dumps(snapshot, ensure_ascii=False, indent=2))
        print(f"Log gespeichert: {iter_log_path}")

        maybe_sync_to_github(config, iter_label, log_dir)
        last_iteration_label = iter_label

        for report in patch_report:
            if report.changed:
                print(f"\n--- DIFF {report.file} ---\n{report.diff}\n")

        print(f"Regel-Check: {rules_msg}")
        print(f"Evaluation: {evaluation.decision} – {evaluation.reason}")

        if rules_ok and evaluation.decision == "success":
            print("\n✅ SUCCESS: Erfolgsbedingungen erfüllt.")
            break

        if iteration == max_iters:
            print("\n⚠️ MAX_ITERS erreicht – Abbruch.")
            break

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    history_path = log_dir / "history.json"
    write_text(history_path, json.dumps(history, ensure_ascii=False, indent=2))
    print(f"\nGesamthistorie gespeichert: {history_path}")

    if last_iteration_label:
        maybe_sync_to_github(
            config,
            last_iteration_label,
            log_dir,
            extra_paths=["{log_dir}/history.json"],
            use_config_paths=False,
        )

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
