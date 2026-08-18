from django.urls import path
from . import views

app_name = 'workorders'

urlpatterns = [
    path('', views.work_order_list, name='list'),
    path('calculator/', views.bandwidth_calculator, name='calculator'),
    path('create/<int:feasibility_pk>/', views.create_work_order, name='create'),
    path('<int:pk>/', views.work_order_detail, name='detail'),
    path('<int:pk>/edit/', views.edit_work_order, name='edit'),
    path('<int:pk>/delete/', views.delete_work_order, name='delete'),
    path('<int:pk>/print/', views.print_work_order, name='print'),
    path('<int:pk>/status/', views.update_status, name='update_status'),
    path('<int:pk>/stage/', views.wo_stage_action, name='stage_action'),
    path('<int:pk>/notify/', views.send_notifications, name='send_notifications'),
    path('<int:pk>/attachments/<int:doc_pk>/', views.attachment_download, name='attachment_download'),
]
