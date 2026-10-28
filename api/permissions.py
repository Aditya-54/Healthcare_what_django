from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Allow access only if the object's created_by matches the request user."""

    def has_object_permission(self, request, view, obj):
        return obj.created_by == request.user
