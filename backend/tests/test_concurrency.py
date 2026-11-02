from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connections
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services import set_temporary_password

from .conftest import PASSWORD, login, post


@pytest.mark.django_db(transaction=True)
def test_temporary_password_can_only_be_consumed_once_concurrently(users):
    user = users["user"]
    password = set_temporary_password(user)
    user.save()
    barrier = Barrier(2)

    def attempt():
        try:
            client = APIClient(enforce_csrf_checks=True)
            barrier.wait(timeout=10)
            return login(client, "user", password).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == [200, 403]


@pytest.mark.django_db(transaction=True)
def test_two_admins_cannot_both_deactivate_themselves_concurrently(users):
    User.objects.filter(pk=users["user"].pk).update(system_role="ADMIN")
    barrier = Barrier(2)

    def attempt(username):
        try:
            client = APIClient(enforce_csrf_checks=True)
            assert login(client, username).status_code == 200
            target = User.objects.get(username=username)
            detail = client.get(f"/api/v1/admin/users/{target.pk}/")
            barrier.wait(timeout=10)
            return post(
                client,
                f"/api/v1/admin/users/{target.pk}/deactivate/",
                {"current_password": PASSWORD},
                HTTP_IF_MATCH=detail["ETag"],
            ).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["admin", "user"]))
    assert sorted(results) == [200, 409]
    assert User.objects.filter(is_active=True, system_role="ADMIN").count() == 1
