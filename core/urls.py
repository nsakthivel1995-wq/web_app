from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('auth/', views.auth_view, name='auth'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/place-order/', views.place_order, name='place_order'),
    path('dashboard/place-quote/', views.place_quote, name='place_quote'),
    path('dashboard/edit-order/<str:order_type>/<int:pk>/', views.edit_order, name='edit_order'),
    path('dashboard/edit-quote/<str:quote_type>/<int:pk>/', views.edit_quote, name='edit_quote'),
    path('dashboard/update-profile/', views.update_profile, name='update_profile'),
    path('contact/', views.contact_submit, name='contact_submit'),

    # Client workflow actions — Step 3 (accept/reject/modify quote),
    # Steps 5–7 (approve design / request correction / pay)
    path('dashboard/quote/<str:quote_type>/<int:pk>/<str:action>/', views.client_quote_action, name='client_quote_action'),
    path('dashboard/order/<str:order_type>/<int:pk>/<str:action>/', views.client_order_action, name='client_order_action'),
    path('download/<str:order_type>/<int:pk>/', views.download_final, name='download_final'),

    # Billing — printable invoice / receipt (owner or staff)
    path('invoice/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('receipt/<int:pk>/', views.receipt_detail, name='receipt_detail'),

    # Staff admin page (custom-styled, not Django /admin/)
    path('staff-admin/', views.admin_dashboard, name='admin_dashboard'),
    path('staff-admin/order/<str:order_type>/<int:pk>/edit/', views.admin_order_edit, name='admin_order_edit'),
    path('staff-admin/quote/<str:quote_type>/<int:pk>/edit/', views.admin_quote_edit, name='admin_quote_edit'),
    path('staff-admin/invoice/new/', views.admin_invoice_create, name='admin_invoice_create'),
    path('staff-admin/invoice/<int:pk>/edit/', views.admin_invoice_edit, name='admin_invoice_edit'),
    path('staff-admin/invoice/<int:pk>/mark-paid/', views.admin_invoice_mark_paid, name='admin_invoice_mark_paid'),
]
