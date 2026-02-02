"""
Views for the Grocify inventory management application.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta, date
import re
import random

from .models import FoodItem
from .forms import CustomUserCreationForm, LoginForm, FoodItemForm
from .api_utils import get_recipe_suggestions, get_recipe_details, check_ingredient_match


# Public views
def home(request):
    """Home page view - the first page users see"""
    context = {
        'page_title': 'Welcome to Grocify',
        'welcome_message': 'Your Smart Kitchen Inventory Manager',
        'features': [
            'Track food items and expiry dates',
            'Get recipe suggestions based on what you have',
            'Reduce food waste and save money',
            'Plan meals efficiently',
        ]
    }
    return render(request, 'home.html', context)


def about(request):
    """About page view"""
    return render(request, 'about.html', {'page_title': 'About Grocify'})


def signup_view(request):
    """
    User registration view
    User must login separately after signup
    """
    if request.user.is_authenticated:
        messages.info(request, 'You are already logged in!')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # Save the user but DO NOT log them in automatically
            user = form.save()
            
            # Get user info for success message
            username = form.cleaned_data.get('username')
            email = form.cleaned_data.get('email')
            
            # Show success message and redirect to login page
            messages.success(
                request, 
                f'Account created successfully for {username}! '
                f'Please login with your credentials to continue.'
            )
            
            # Redirect to login page
            return redirect('login')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'auth/signup.html', {'form': form, 'page_title': 'Sign Up'})


def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        messages.info(request, 'You are already logged in!')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                
                # Check for 'next' parameter to redirect to intended page
                next_page = request.GET.get('next', 'dashboard')
                return redirect(next_page)
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LoginForm()
    
    return render(request, 'auth/login.html', {'form': form, 'page_title': 'Login'})


def logout_view(request):
    """User logout view"""
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, 'You have been logged out.')
    return redirect('home')


# Protected views (require login)
@login_required
def dashboard(request):
    """User dashboard - only accessible when logged in"""
    user_items = FoodItem.objects.filter(user=request.user)
    
    # Get today's date
    today = date.today()
    
    # Calculate stats
    total_items = user_items.count()
    
    # Calculate expiring and expired items
    expiring_items_list = []
    expired_items_list = []
    expiring_soon_count = 0
    expired_count = 0
    today_count = 0
    tomorrow_count = 0
    this_week_count = 0
    
    for item in user_items:
        if item.expiry_date:
            days_until = (item.expiry_date - today).days
            
            if days_until < 0:
                expired_count += 1
                expired_items_list.append(item)
            elif days_until == 0:
                today_count += 1
                expiring_soon_count += 1
                expiring_items_list.append(item)
            elif 1 <= days_until <= 3:
                expiring_soon_count += 1
                expiring_items_list.append(item)
            
            # For this week count (0-7 days, including today)
            if 0 <= days_until <= 7:
                this_week_count += 1
            
            # For tomorrow count
            if days_until == 1:
                tomorrow_count += 1
    
    # Sort by expiry date (closest first)
    expiring_items_list.sort(key=lambda x: x.expiry_date)
    expired_items_list.sort(key=lambda x: x.expiry_date)
    
    # Limit to 5 items each
    expiring_items = expiring_items_list[:5]
    expired_items_display = expired_items_list[:5]
    
    # Recent items
    recent_items = user_items.order_by('-added_date')[:5]
    
    # Expiry summary
    expiry_summary = {
        'expired': expired_count,
        'today': today_count,
        'tomorrow': tomorrow_count,
        'this_week': this_week_count,
    }
    
    context = {
        'page_title': 'Dashboard',
        'user': request.user,
        'total_items': total_items,
        'expiring_soon': expiring_soon_count,
        'expired_items': expired_count,
        'recent_items': recent_items,
        'expiring_items': expiring_items,
        'expired_items_list': expired_items_display,
        'expiry_summary': expiry_summary,
        'today': today,
    }
    
    return render(request, 'dashboard.html', context)


@login_required
def inventory_list(request):
    """List all inventory items for the logged-in user"""
    user_items = FoodItem.objects.filter(user=request.user)
    
    # Get today's date for calculations
    today = date.today()
    
    # Get filter from request
    category_filter = request.GET.get('category', '')
    if category_filter:
        user_items = user_items.filter(category=category_filter)
    
    # Get search query
    search_query = request.GET.get('search', '')
    if search_query:
        user_items = user_items.filter(name__icontains=search_query)
    
    # Order by expiry date (closest first)
    user_items = user_items.order_by('expiry_date', 'name')
    
    # Calculate stats for the inventory page
    expired_count = 0
    expiring_soon_count = 0
    
    for item in user_items:
        if item.expiry_date:
            days_until = (item.expiry_date - today).days
            if days_until < 0:
                expired_count += 1
            elif 0 <= days_until <= 3:
                expiring_soon_count += 1
    
    context = {
        'page_title': 'My Inventory',
        'items': user_items,
        'categories': FoodItem.CATEGORY_CHOICES,
        'selected_category': category_filter,
        'search_query': search_query,
        'expired_count': expired_count,
        'expiring_soon_count': expiring_soon_count,
        'total_count': user_items.count(),
    }
    return render(request, 'inventory/list.html', context)


@login_required
def add_item(request):
    """Add a new food item"""
    if request.method == 'POST':
        form = FoodItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
            item.save()
            
            # Update expiry status
            item.update_expiry_status()
            
            messages.success(request, f'"{item.name}" added to your inventory!')
            return redirect('inventory_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Set default expiry date to 7 days from now
        initial_date = date.today() + timedelta(days=7)
        form = FoodItemForm(initial={'expiry_date': initial_date})
    
    context = {
        'page_title': 'Add Food Item',
        'form': form,
    }
    return render(request, 'inventory/add_item.html', context)


@login_required
def edit_item(request, item_id):
    """Edit an existing food item"""
    item = get_object_or_404(FoodItem, id=item_id, user=request.user)
    
    if request.method == 'POST':
        form = FoodItemForm(request.POST, instance=item)
        if form.is_valid():
            updated_item = form.save()
            # Update expiry status
            updated_item.update_expiry_status()
            
            messages.success(request, f'"{updated_item.name}" updated successfully!')
            return redirect('inventory_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = FoodItemForm(instance=item)
    
    context = {
        'page_title': 'Edit Food Item',
        'form': form,
        'item': item,
    }
    return render(request, 'inventory/edit_item.html', context)


@login_required
def delete_item(request, item_id):
    """Delete a food item"""
    item = get_object_or_404(FoodItem, id=item_id, user=request.user)
    
    if request.method == 'POST':
        item_name = item.name
        item.delete()
        messages.success(request, f'"{item_name}" removed from inventory.')
        return redirect('inventory_list')
    
    # If GET request, show confirmation page
    context = {
        'page_title': 'Delete Item',
        'item': item,
    }
    return render(request, 'inventory/delete_item.html', context)


@login_required
def delete_item_ajax(request, item_id):
    """AJAX endpoint for deleting items"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        item = get_object_or_404(FoodItem, id=item_id, user=request.user)
        item_name = item.name
        item.delete()
        return JsonResponse({
            'success': True, 
            'message': f'"{item_name}" has been deleted successfully.'
        })
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)


@login_required
def recipes(request):
    """Recipe suggestions page"""
    user_items = FoodItem.objects.filter(user=request.user)
    total_items = user_items.count()
    
    if total_items == 0:
        # No items in inventory
        recipe_data = {
            'error': 'No food items in your inventory. Add some items to get recipe suggestions.',
            'recipes': []
        }
    else:
        # Get recipe suggestions from API
        recipe_data = get_recipe_suggestions(user_items)
    
    context = {
        'page_title': 'Recipe Suggestions',
        'recipe_data': recipe_data,
        'total_items': total_items,
    }
    return render(request, 'recipes/list.html', context)


@login_required
def recipe_detail(request, recipe_id):
    """Detailed recipe view"""
    # Get user's inventory for ingredient matching
    user_items = FoodItem.objects.filter(user=request.user)
    user_ingredients = [item.name.lower() for item in user_items]
    
    # Get recipe details
    recipe = get_recipe_details(recipe_id)
    
    if not recipe:
        return render(request, 'recipes/detail.html', {
            'recipe': {'error': 'Recipe not found or could not be loaded.'}
        })
    
    # Check which ingredients the user has using SMART matching
    if 'ingredients' in recipe:
        total_ingredients = len(recipe['ingredients'])
        has_count = 0
        
        for ingredient in recipe['ingredients']:
            ingredient_name = ingredient.get('name', '').lower()
            ingredient_has_it = False
            
            # Check if user has this ingredient using SMART matching
            for user_ing in user_ingredients:
                if check_ingredient_match(user_ing, ingredient_name):
                    ingredient_has_it = True
                    break
            
            ingredient['has_it'] = ingredient_has_it
            
            if ingredient_has_it:
                has_count += 1
        
        # Calculate match percentage
        if total_ingredients > 0:
            match_percentage = int((has_count / total_ingredients) * 100)
            
            # Determine feasibility
            if match_percentage >= 80:
                recipe['feasibility'] = 'high'
                recipe['feasibility_text'] = 'You have most ingredients!'
            elif match_percentage >= 50:
                recipe['feasibility'] = 'medium'
                recipe['feasibility_text'] = 'You have many ingredients'
            else:
                recipe['feasibility'] = 'low'
                recipe['feasibility_text'] = 'You need several ingredients'
            
            recipe['ingredients_percentage'] = match_percentage
            recipe['has_count'] = has_count
            recipe['total_count'] = total_ingredients
    
    return render(request, 'recipes/detail.html', {'recipe': recipe})