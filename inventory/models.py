

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import pre_save
from django.dispatch import receiver

class FoodItem(models.Model):
    # Category choices (like dropdown options)
    CATEGORY_CHOICES = [
        ('fruit', 'Fruit'),
        ('vegetable', 'Vegetable'),
        ('dairy', 'Dairy'),
        ('meat', 'Meat'),
        ('grain', 'Grain'),
        ('canned', 'Canned Food'),
        ('beverage', 'Beverage'),
        ('snack', 'Snack'),
        ('spice', 'Spice/Condiment'),
        ('other', 'Other'),
    ]
    
    # Database fields (columns)
    name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit = models.CharField(max_length=50)  # kg, liter, piece, etc.
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    expiry_date = models.DateField()
    added_date = models.DateTimeField(auto_now_add=True)  # Auto-set when added
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Who owns this item
    
    # Extra status field (we'll calculate this later)
    is_expired = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"
    
    # Method to check if item is expiring soon
    def is_expiring_soon(self):
        if self.expiry_date:
            days_left = (self.expiry_date - timezone.now().date()).days
            return 0 <= days_left <= 3  # Expiring in next 3 days
        return False
    
    
    # NEW: Get days until expiry (positive = days left, negative = days expired)
    def days_until_expiry(self):
        if self.expiry_date:
            return (self.expiry_date - timezone.now().date()).days
        return None
    
    # NEW: Get expiry status text
    def get_expiry_status(self):
        if not self.expiry_date:
            return "no-date"
        
        days = self.days_until_expiry()
        
        if days < 0:
            return "expired"
        elif days == 0:
            return "expires-today"
        elif 1 <= days <= 3:
            return "expiring-soon"
        elif 4 <= days <= 7:
            return "expiring-week"
        else:
            return "good"
    
    # NEW: Get expiry status color
    def get_expiry_color(self):
        status = self.get_expiry_status()
        colors = {
            "expired": "#e74c3c",  # Red
            "expires-today": "#e67e22",  # Orange
            "expiring-soon": "#f39c12",  # Yellow
            "expiring-week": "#3498db",  # Blue
            "good": "#2ecc71",  # Green
            "no-date": "#95a5a6",  # Gray
        }
        return colors.get(status, "#95a5a6")
    
    # NEW: Get expiry status icon
    def get_expiry_icon(self):
        status = self.get_expiry_status()
        icons = {
            "expired": "⛔",
            "expires-today": "🔥",
            "expiring-soon": "⚠️",
            "expiring-week": "⏳",
            "good": "✅",
            "no-date": "📅",
        }
        return icons.get(status, "📅")
    
    # NEW: Get expiry status text for display
    def get_expiry_display(self):
        days = self.days_until_expiry()
        
        if days is None:
            return "No expiry date"
        elif days < 0:
            return f"Expired {abs(days)} days ago"
        elif days == 0:
            return "Expires today!"
        elif days == 1:
            return "Expires tomorrow"
        elif 2 <= days <= 3:
            return f"Expires in {days} days"
        elif 4 <= days <= 7:
            return f"Expires in {days} days"
        else:
            return f"Expires in {days} days"
    
    # Method to automatically update is_expired field
    def update_expiry_status(self):
        if self.expiry_date < timezone.now().date():
            self.is_expired = True
        else:
            self.is_expired = False
        self.save()


# ===== SIGNALS =====
@receiver(pre_save, sender=FoodItem)
def update_expiry_status_signal(sender, instance, **kwargs):
    """
    Automatically update is_expired field before saving.
    This ensures the is_expired field is always current.
    """
    if instance.expiry_date:
        instance.is_expired = instance.expiry_date < timezone.now().date()