"""The only place laboratorio runs Docker (the docker CLI, as the former
lab.sh did): an argument list, never a shell; a time limit; output parsed
from --format '{{json .}}'. Tests replace run()."""
import json
import subprocess

from django.conf import settings


class DockerError(Exception):
    def __init__(self, message, stderr=""):
        super().__init__(message)
        self.stderr = stderr


def _timeout():
    return settings.LABORATORIO.get("DOCKER_TIMEOUT", 120)


def run(args, *, input=None, timeout=None, check=True):
    """docker <args>: (returncode, stdout, stderr)."""
    try:
        done = subprocess.run(["docker", *args], input=input, capture_output=True, text=True,
                              timeout=timeout or _timeout(), check=False)
    except FileNotFoundError:
        raise DockerError("Docker is not installed.")
    except subprocess.TimeoutExpired:
        raise DockerError(f"Docker did not answer in time: docker {args[0]}.")
    if check and done.returncode != 0:
        raise DockerError(f"docker {args[0]} failed.", stderr=(done.stderr or "").strip()[-2000:])
    return done.returncode, done.stdout, done.stderr


def ok(args):
    return run(args, check=False)[0] == 0


def json_lines(args):
    _, out, _ = run(args)
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def container_exists(name):
    return ok(["container", "inspect", name])


def container_running(name):
    code, out, _ = run(["inspect", "--format", "{{.State.Running}}", name], check=False)
    return code == 0 and out.strip() == "true"


def image_exists(image):
    return ok(["image", "inspect", image])


def volume_exists(name):
    return ok(["volume", "inspect", name])


def network_exists(name):
    return ok(["network", "inspect", name])


def published_port(container, internal):
    code, out, _ = run(["port", container, f"{internal}/tcp"], check=False)
    if code != 0 or not out.strip():
        return None
    port = out.splitlines()[0].rsplit(":", 1)[-1].strip()
    return int(port) if port.isdigit() else None


def container_networks(container):
    code, out, _ = run(["inspect", "--format", "{{json .NetworkSettings.Networks}}", container], check=False)
    if code != 0 or not out.strip() or out.strip() == "null":
        return []
    return list(json.loads(out))


def network_container_count(network):
    code, out, _ = run(["network", "inspect", "--format", "{{len .Containers}}", network], check=False)
    return int(out.strip()) if code == 0 and out.strip().isdigit() else 1


def managed(kind):
    """Names of the Docker objects laboratorio manages (label lab.manager=true):
    kind is ps (containers, -a), network or volume."""
    if kind == "ps":
        args = ["ps", "-a", "--filter", "label=lab.manager=true", "--format", "{{.Names}}"]
    else:
        args = [kind, "ls", "--filter", "label=lab.manager=true", "--format", "{{.Name}}"]
    _, out, _ = run(args)
    return [line.strip() for line in out.splitlines() if line.strip()]


def volume_users(volume):
    _, out, _ = run(["ps", "-a", "--filter", f"volume={volume}", "-q"])
    return len([line for line in out.splitlines() if line.strip()])


def stats(containers):
    if not containers:
        return []
    return json_lines(["stats", "--no-stream", "--format", "{{json .}}", *containers])


def images():
    return json_lines(["images", "--format", "{{json .}}"])
