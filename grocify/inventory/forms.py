from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import FoodItem
from django.utils import timezone

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

class FoodItemForm(forms.ModelForm):
    # Customize the expiry_date field to show a date picker
    expiry_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=timezone.now().date()  # Default to today
    )
    
    class Meta:
        model = FoodItem
        fields = ['name', 'quantity', 'unit', 'category', 'expiry_date']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g., Apples, Milk, Bread'}),
            'quantity': forms.NumberInput(attrs={'min': 1}),
            'unit': forms.TextInput(attrs={'placeholder': 'e.g., kg, liters, pieces'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make fields more user-friendly
        self.fields['category'].widget.attrs.update({'class': 'category-select'})