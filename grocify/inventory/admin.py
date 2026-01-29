from django.contrib import admin
from .models import FoodItem

@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'quantity', 'unit', 'category', 'expiry_date', 'user', 'is_expired')
    list_filter = ('category', 'is_expired', 'expiry_date')
    search_fields = ('name',)
    date_hierarchy = 'expiry_date'
