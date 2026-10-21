"""Security headers that Django's SecurityMiddleware does not set."""

# The API returns JSON and the admin is server-rendered, so nothing may be framed,
# embedded or loaded from another origin. Ninja's /api/docs serves its assets locally.
CSP = "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'"


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", CSP)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.path.startswith("/api/"):
            # Responses carry one person's data (even 401s): a shared cache must never keep them. Views may override.
            response.setdefault("Cache-Control", "no-store")
        return response
