from django.contrib.auth.models import User
from django.test import TestCase

from accounts_dept.models import Role
from accounts_dept.permissions import ensure_roles, get_or_create_profile
from feasibility.models import FeasibilityRequest, ServiceLine


def make_user(username, role_slug, password='pass'):
    ensure_roles()
    user = User.objects.create_user(username, password=password)
    profile = get_or_create_profile(user)
    profile.role = Role.objects.get(slug=role_slug)
    profile.save()
    return user


def make_frq(user, **kwargs):
    defaults = {
        'customer_name': 'Acme ISP',
        'contact_person': 'Jane Doe',
        'phone_number': '01700000000',
        'address': 'Dhaka',
        'latitude': 23.8103,
        'longitude': 90.4125,
        'requested_capacity': 100,
        'submitted_by': user,
        'status': 'feasible',
        'onboarding_status': '',
    }
    defaults.update(kwargs)
    return FeasibilityRequest.objects.create(**defaults)


def make_wo(user, **kwargs):
    kwargs.setdefault('onboarding_status', 'submitted')
    kwargs.setdefault('nid_number', '1234567890')
    fr = make_frq(user, **kwargs)
    ServiceLine.objects.create(
        request=fr, service_type='IPT', capacity_mbps=100, unit_price=100, quantity=1,
    )
    return fr


class LogoutTests(TestCase):
    def setUp(self):
        self.user = make_user('sales1', 'sales')

    def test_get_logout_rejected(self):
        self.client.login(username='sales1', password='pass')
        response = self.client.get('/accounts/logout/')
        self.assertEqual(response.status_code, 405)

    def test_post_logout_works(self):
        self.client.login(username='sales1', password='pass')
        response = self.client.post('/accounts/logout/')
        self.assertIn(response.status_code, (200, 302))
        follow = self.client.get('/workorders/')
        self.assertEqual(follow.status_code, 302)
        self.assertIn('/accounts/login/', follow.url)


class MediaAuthTests(TestCase):
    def test_anonymous_media_redirects_to_login(self):
        response = self.client.get('/media/onboarding_docs/does-not-exist.pdf')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
