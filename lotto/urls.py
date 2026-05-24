from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('buy/', views.buy_ticket, name='buy_ticket'),
    path('my-tickets/', views.my_tickets, name='my_tickets'),
    path('check/<int:ticket_id>/', views.check_win, name='check_win'),
    path('check-all/', views.check_all_wins, name='check_all_wins'),
    path('history/', views.draw_history, name='draw_history'),
    # Admin
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/draw/<int:round_id>/', views.admin_draw, name='admin_draw'),
    path('admin-panel/sales/', views.admin_sales, name='admin_sales'),
    path('admin-panel/winners/', views.admin_winners, name='admin_winners'),
    path('admin-panel/create-round/', views.create_round, name='create_round'),
]
