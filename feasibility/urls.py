from django.urls import path
from . import views

app_name = 'feasibility'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('new/', views.create_request, name='create'),
    path('geo/districts/', views.geo_districts, name='geo_districts'),
    path('geo/upazilas/', views.geo_upazilas, name='geo_upazilas'),
    path('work-order/create/', views.work_order_candidates, name='work_order_create'),
    path('onboarding/', views.onboarding_list, name='onboarding_list'),
    path('<int:pk>/edit/', views.edit_request, name='edit'),
    path('<int:pk>/', views.request_detail, name='detail'),
    path('<int:pk>/review/', views.review_request, name='review'),
    path('<int:pk>/report/client/', views.client_report, name='client_report'),
    path('<int:pk>/report/internal/', views.internal_report, name='internal_report'),
    path('<int:pk>/onboard/', views.start_onboarding, name='start_onboarding'),
    path('<int:pk>/onboard/edit/', views.edit_onboarding, name='edit_onboarding'),
    path('<int:pk>/onboard/detail/', views.onboarding_detail, name='onboarding_detail'),
    path('<int:pk>/onboard/status/', views.update_onboarding_status, name='update_onboarding_status'),
    path('<int:pk>/onboard/notify/', views.send_notifications, name='send_notifications'),
    path('<int:pk>/bandwidth/', views.bandwidth_list, name='bandwidth_list'),
    path('<int:pk>/bandwidth/add/', views.add_bandwidth, name='add_bandwidth'),
    path('<int:pk>/bandwidth/<str:provider>/delete/', views.delete_bandwidth, name='delete_bandwidth'),
    # NTTN Provider Feedback & Comparison
    path('<int:pk>/providers/compare/', views.provider_comparison, name='provider_comparison'),
    path('<int:pk>/providers/compare/print/', views.provider_comparison_print, name='provider_comparison_print'),
    path('<int:pk>/providers/<int:provider_pk>/response/', views.provider_response_add, name='provider_response_add'),
    path('<int:pk>/providers/response/<int:response_pk>/delete/', views.provider_response_delete, name='provider_response_delete'),
    path('<int:pk>/providers/attachments/<int:attachment_pk>/', views.nttn_attachment_download, name='nttn_attachment_download'),
]
