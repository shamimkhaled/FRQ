from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('audit/', views.audit_log_list, name='audit_log'),
    path('notifications/', views.notification_list, name='notifications'),
    path('notifications/read-all/', views.notification_mark_all, name='notifications_read_all'),
    path('notifications/<int:pk>/', views.notification_open, name='notification_open'),
]
