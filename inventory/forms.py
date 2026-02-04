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
    
    # Add unit choices for dropdown
    UNIT_CHOICES = [
        ('', 'Select unit or type custom'),  # Empty choice
        ('kg', 'Kilograms (kg)'),
        ('g', 'Grams (g)'),
        ('l', 'Liters (l)'),
        ('ml', 'Milliliters (ml)'),
        ('pieces', 'Pieces'),
        ('dozens', 'Dozens'),
        ('pack', 'Pack'),
        ('bottle', 'Bottle'),
        ('can', 'Can'),
        ('box', 'Box'),
        ('bunch', 'Bunch'),
        ('cup', 'Cup'),
        ('tsp', 'Teaspoon (tsp)'),
        ('tbsp', 'Tablespoon (tbsp)'),
    ]
    
    unit = forms.ChoiceField(
        choices=UNIT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'unit-select'})
    )
    
    # Add custom unit field for manual entry
    custom_unit = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Or type custom unit...',
            'class': 'custom-unit-input',
            'style': 'display: none;'  # Hidden by default
        })
    )
    
    class Meta:
        model = FoodItem
        fields = ['name', 'quantity', 'category', 'expiry_date']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g., Apples, Milk, Bread'}),
            'quantity': forms.NumberInput(attrs={'min': 1, 'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make fields more user-friendly
        self.fields['category'].widget.attrs.update({'class': 'category-select'})
        
        # If editing an existing item, set initial values
        if self.instance and self.instance.pk:
            if self.instance.unit and self.instance.unit not in dict(self.UNIT_CHOICES).keys():
                # If unit is custom, show it in custom field
                self.fields['custom_unit'].initial = self.instance.unit
                self.fields['unit'].initial = ''
    
    def clean(self):
        cleaned_data = super().clean()
        unit = cleaned_data.get('unit')
        custom_unit = cleaned_data.get('custom_unit')
        
        # Determine which unit to use
        if custom_unit and custom_unit.strip():
            cleaned_data['unit'] = custom_unit.strip()
        elif unit:
            cleaned_data['unit'] = unit
        else:
            self.add_error('unit', 'Please select a unit or enter a custom unit')
        
        return cleaned_data