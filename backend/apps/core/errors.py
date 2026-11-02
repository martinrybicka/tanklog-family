from django.http import JsonResponse
from rest_framework.exceptions import APIException, NotAuthenticated, ValidationError


class Problem(APIException):
    def __init__(self, code, message, status=400):
        self.status_code = status
        super().__init__(detail=message, code=code)


def error_body(code, message, request, fields=None):
    return {
        "error": {
            "code": code,
            "message": message,
            "fields": fields or {},
            "request_id": getattr(request, "request_id", ""),
        }
    }


def exception_handler(exc, context):
    from rest_framework.views import exception_handler as drf_exception_handler

    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    code = getattr(exc, "default_code", "error")
    if isinstance(exc, Problem):
        code = exc.get_codes()
    if isinstance(exc, NotAuthenticated):
        code = "authentication_required"
    if isinstance(exc, ValidationError):
        code = "validation_error"
    detail = response.data
    fields = detail if isinstance(detail, dict) and "detail" not in detail else {}
    message = (
        str(detail.get("detail", "Zkontrolujte zadané údaje."))
        if isinstance(detail, dict)
        else "Zkontrolujte zadané údaje."
    )
    response.data = error_body(code, message, context["request"], fields)
    return response


def csrf_failure(request, reason=""):
    return JsonResponse(
        error_body("csrf_failed", "Platnost formuláře vypršela. Obnovte stránku a zkuste to znovu.", request),
        status=403,
    )


def axes_lockout(request, credentials=None, *args, **kwargs):
    response = JsonResponse(
        error_body("login_locked", "Příliš mnoho pokusů. Zkuste přihlášení za 15 minut.", request), status=429
    )
    response["Retry-After"] = "900"
    return response


def not_found(request, exception=None):
    return JsonResponse(error_body("not_found", "Požadovaná adresa neexistuje.", request), status=404)


def server_error(request):
    return JsonResponse(error_body("server_error", "Požadavek se nepodařilo dokončit.", request), status=500)
