"""
URL configuration for grocify project.
"""
from django.contrib import admin
from django.urls import path, include
from inventory import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('inventory/', views.inventory_list, name='inventory_list'),
    path('inventory/add/', views.add_item, name='add_item'),
    path('inventory/edit/<int:item_id>/', views.edit_item, name='edit_item'),
    path('inventory/delete/<int:item_id>/', views.delete_item, name='delete_item'),
    path('inventory/delete/<int:item_id>/ajax/', views.delete_item_ajax, name='delete_item_ajax'),
    # Recipe URLs
    path('recipes/', views.recipes, name='recipes'),
    path('recipes/<str:recipe_id>/', views.recipe_detail, name='recipe_detail'),
]