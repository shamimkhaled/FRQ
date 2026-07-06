from django.urls import path
from . import views

app_name = 'capacity'

urlpatterns = [
    path('<int:feasibility_pk>/', views.capacity_list, name='list'),
    path('<int:feasibility_pk>/add/', views.add_capacity_confirmation, name='add'),
    path('<int:feasibility_pk>/<int:pk>/edit/', views.edit_capacity_confirmation, name='edit'),
    path('<int:feasibility_pk>/<int:pk>/delete/', views.delete_capacity_confirmation, name='delete'),
    path('<int:feasibility_pk>/pricing/', views.pricing_list, name='pricing_list'),
    path('<int:feasibility_pk>/pricing/add/', views.add_pricing, name='add_pricing'),
    path('<int:feasibility_pk>/pricing/<int:pk>/edit/', views.edit_pricing, name='edit_pricing'),
    path('<int:feasibility_pk>/pricing/<int:pk>/delete/', views.delete_pricing, name='delete_pricing'),
    path('<int:feasibility_pk>/send-emails/', views.send_bw_emails, name='send_bw_emails'),
]
