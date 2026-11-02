from rest_framework.permissions import BasePermission

from apps.core.errors import Problem


class SessionRequired(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            raise Problem("authentication_required", "Přihlaste se pro pokračování.", 403)
        return True


class FullSession(SessionRequired):
    def has_permission(self, request, view):
        super().has_permission(request, view)
        if request.user.must_change_password or request.session.get("password_change_only"):
            raise Problem("password_change_required", "Nejdříve nastavte vlastní heslo.", 403)
        return True


class Administrator(FullSession):
    def has_permission(self, request, view):
        super().has_permission(request, view)
        return request.user.system_role == "ADMIN"
