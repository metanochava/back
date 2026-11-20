"""/api/ensino/... keeps answering for one release (the app is now
"academica", docs/progress/ensino-modular.md): the request is handled by the
same view under /api/academica/... - same authentication, permissions and
tenant scope. Remove once no client calls the old paths."""
from django.http import Http404
from django.urls import Resolver404, resolve


def ensino_alias(request, rest=""):
    path = f"/api/academica/{rest}"
    try:
        match = resolve(path)
    except Resolver404:
        raise Http404
    request.path_info = path
    return match.func(request, *match.args, **match.kwargs)
