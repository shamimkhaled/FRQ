from django.test import TestCase
from django.urls import reverse

from accounts_dept.tests import make_frq, make_user
from feasibility.models import NTTNProvider, NTTNProviderResponse
from feasibility.nttn_utils import seed_default_providers


class NttnAccessTests(TestCase):
    def setUp(self):
        self.sales_a = make_user('sales_nttn_a', 'sales')
        self.sales_b = make_user('sales_nttn_b', 'sales')
        self.nttn = make_user('nttn_user', 'nttn_team')
        self.fr = make_frq(self.sales_a)
        seed_default_providers()
        self.provider = NTTNProvider.objects.filter(is_active=True).first()
        self.resp = NTTNProviderResponse.objects.create(
            feasibility_request=self.fr,
            provider=self.provider,
            status='pending',
        )

    def test_get_does_not_delete_provider_response(self):
        self.client.login(username='nttn_user', password='pass')
        response = self.client.get(
            reverse('feasibility:provider_response_delete', args=[self.fr.pk, self.resp.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(NTTNProviderResponse.objects.filter(pk=self.resp.pk).exists())

    def test_sales_cannot_print_another_users_comparison(self):
        self.client.login(username='sales_nttn_b', password='pass')
        response = self.client.get(reverse('feasibility:provider_comparison_print', args=[self.fr.pk]))
        self.assertIn(response.status_code, (302, 403))
