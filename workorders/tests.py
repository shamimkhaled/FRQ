from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts_dept.permissions import user_can_edit_wo
from accounts_dept.tests import make_user, make_wo
from feasibility.models import OnboardingDocument, UpstreamProvider
from feasibility.utils import parse_services_from_post
from workorders.utils import seed_default_upstream_providers
from workorders.workflow import apply_stage_action


class SalesIsolationTests(TestCase):
    def setUp(self):
        self.sales_a = make_user('sales_a', 'sales')
        self.sales_b = make_user('sales_b', 'sales')
        self.wo = make_wo(self.sales_a)

    def test_sales_cannot_print_another_users_work_order(self):
        self.client.login(username='sales_b', password='pass')
        response = self.client.get(reverse('workorders:print', args=[self.wo.pk]))
        self.assertEqual(response.status_code, 403)

    def test_owner_can_print_own_work_order(self):
        self.client.login(username='sales_a', password='pass')
        response = self.client.get(reverse('workorders:print', args=[self.wo.pk]))
        self.assertEqual(response.status_code, 200)

    def test_list_hides_other_sales_work_orders(self):
        self.client.login(username='sales_b', password='pass')
        response = self.client.get(reverse('workorders:list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.wo.display_name)


class WorkflowBypassTests(TestCase):
    def setUp(self):
        self.sales = make_user('sales_w', 'sales')
        self.noc = make_user('noc_w', 'noc')
        self.wo = make_wo(self.sales)

    def test_edit_form_ignores_onboarding_status_post(self):
        self.client.login(username='sales_w', password='pass')
        seed_default_upstream_providers()
        provider = UpstreamProvider.objects.filter(is_active=True).exclude(code='others').first()
        response = self.client.post(reverse('workorders:edit', args=[self.wo.pk]), {
            'nid_number': '1234567890',
            'email': 'a@example.com',
            'billing_date': date.today().isoformat(),
            'upstream_provider': provider.pk if provider else '',
            'requested_capacity': 100,
            'wo_vat_percent': 15,
            'wo_discount': 0,
            'wo_client_share_percent': 50,
            'customer_category': 'BW',
            'onboarding_status': 'activated',
            'service_0_type': 'IPT',
            'service_0_capacity': 100,
            'service_0_unit_price': 100,
            'service_0_quantity': 1,
        })
        self.wo.refresh_from_db()
        self.assertEqual(self.wo.onboarding_status, 'submitted')
        self.assertNotEqual(response.status_code, 500)

    def test_approver_cannot_override_status(self):
        self.client.login(username='noc_w', password='pass')
        response = self.client.post(reverse('workorders:update_status', args=[self.wo.pk]), {
            'status': 'activated',
        })
        self.wo.refresh_from_db()
        self.assertEqual(self.wo.onboarding_status, 'submitted')
        self.assertNotEqual(response.status_code, 500)

    def test_noc_cannot_edit_after_accounts_approved(self):
        self.wo.onboarding_status = 'accounts_approved'
        self.wo.save(update_fields=['onboarding_status'])
        self.assertFalse(user_can_edit_wo(self.noc, self.wo))


class StageTransitionTests(TestCase):
    def setUp(self):
        self.sales = make_user('sales_s', 'sales')
        self.accounts = make_user('acc_s', 'accounts')
        self.wo = make_wo(self.sales)

    def test_accounts_approve_moves_to_management(self):
        ok, status = apply_stage_action(self.wo, self.accounts, 'accounts', 'approve', 'ok')
        self.assertTrue(ok)
        self.assertEqual(status, 'accounts_approved')
        self.wo.refresh_from_db()
        self.assertEqual(self.wo.onboarding_status, 'accounts_approved')


class ServiceParseTests(TestCase):
    def test_rejects_unknown_service_type(self):
        services = parse_services_from_post({
            'customer_category': 'BW',
            'service_0_type': 'HACK',
            'service_0_capacity': '100',
            'service_0_unit_price': '1',
            'service_0_quantity': '1',
            'service_2_type': 'IPT',
            'service_2_capacity': '50',
            'service_2_unit_price': '100',
            'service_2_quantity': '1',
        })
        self.assertEqual(len(services), 1)
        self.assertEqual(services[0]['service_type'], 'IPT')


@override_settings(MEDIA_ROOT='/tmp/frq-test-media')
class AttachmentAclTests(TestCase):
    def setUp(self):
        self.sales_a = make_user('sales_att_a', 'sales')
        self.sales_b = make_user('sales_att_b', 'sales')
        self.wo = make_wo(self.sales_a)
        self.doc = OnboardingDocument.objects.create(
            request=self.wo,
            doc_type='other',
            file=SimpleUploadedFile('nid.pdf', b'%PDF-1.4 test', content_type='application/pdf'),
        )

    def test_other_sales_cannot_download_attachment(self):
        self.client.login(username='sales_att_b', password='pass')
        response = self.client.get(reverse('workorders:attachment_download', args=[self.wo.pk, self.doc.pk]))
        self.assertEqual(response.status_code, 403)

    def test_owner_can_download_attachment(self):
        self.client.login(username='sales_att_a', password='pass')
        response = self.client.get(reverse('workorders:attachment_download', args=[self.wo.pk, self.doc.pk]))
        self.assertEqual(response.status_code, 200)
