from .api_utils import get_recipe_suggestions
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .forms import CustomUserCreationForm, LoginForm, FoodItemForm
from .models import FoodItem
from django.utils import timezone
from datetime import timedelta

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
    """User registration view"""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully! Welcome to Grocify!')
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'auth/signup.html', {'form': form, 'page_title': 'Sign Up'})

def login_view(request):
    """User login view"""
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    
    return render(request, 'auth/login.html', {'form': form, 'page_title': 'Login'})

def logout_view(request):
    """User logout view"""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')

# Protected views (require login)
@login_required
def dashboard(request):
    """User dashboard - only accessible when logged in"""
    from datetime import date, timedelta
    
    user_items = FoodItem.objects.filter(user=request.user)
    
    # Get today's date - FIXED VERSION
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
    
    # Recent items (excluding expiring/expired)
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
        # Add expiry data
        'expiring_items': expiring_items,
        'expired_items_list': expired_items_display,
        'expiry_summary': expiry_summary,
        'today': today,  # This should now have a value
    }
    
    
    
    return render(request, 'dashboard.html', context)
    
  

@login_required
def inventory_list(request):
    """List all inventory items for the logged-in user"""
    user_items = FoodItem.objects.filter(user=request.user).order_by('expiry_date')
    
    # Get filter from request
    category_filter = request.GET.get('category', '')
    if category_filter:
        user_items = user_items.filter(category=category_filter)
    
    # Get search query
    search_query = request.GET.get('search', '')
    if search_query:
        user_items = user_items.filter(name__icontains=search_query)
    
    context = {
        'page_title': 'My Inventory',
        'items': user_items,
        'categories': FoodItem.CATEGORY_CHOICES,
        'selected_category': category_filter,
        'search_query': search_query,
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
        form = FoodItemForm()
    
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
    if request.method == 'DELETE' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        item = get_object_or_404(FoodItem, id=item_id, user=request.user)
        item.delete()
        return JsonResponse({'success': True, 'message': 'Item deleted successfully'})
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)

@login_required
def recipes(request):
    """Recipe suggestions page"""
    user_items = FoodItem.objects.filter(user=request.user)
    
    # Get recipe suggestions
    recipe_data = get_recipe_suggestions(user_items)
    
    context = {
        'page_title': 'Recipe Suggestions',
        'recipe_data': recipe_data,
        'user_items': user_items,
        'total_items': user_items.count(),
    }
    return render(request, 'recipes/list.html', context)

@login_required
def recipe_detail(request, recipe_id):
    """Detailed recipe view with actual data from TheMealDB"""
    import requests
    from django.core.cache import cache
    
    # Check cache first
    cache_key = f"recipe_detail_{recipe_id}"
    recipe_data = cache.get(cache_key)
    
    if not recipe_data:
        # Fetch recipe details from TheMealDB API
        try:
            url = "https://www.themealdb.com/api/json/v1/1/lookup.php"
            params = {'i': recipe_id}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                meals = data.get('meals', [])
                
                if meals:
                    meal = meals[0]
                    
                    # Extract ingredients and measures
                    ingredients = []
                    for i in range(1, 21):  # TheMealDB has up to 20 ingredients
                        ingredient = meal.get(f'strIngredient{i}', '').strip()
                        measure = meal.get(f'strMeasure{i}', '').strip()
                        
                        if ingredient:
                            ingredients.append({
                                'name': ingredient,
                                'measure': measure
                            })
                    
                    # Get user's inventory items for comparison
                    user_items = FoodItem.objects.filter(user=request.user)
                    user_ingredients = [item.name.lower() for item in user_items]
                    
                    # Check which ingredients user has
                    for ingredient in ingredients:
                        ingredient_name = ingredient['name'].lower()
                        ingredient['has_it'] = any(
                            user_ing in ingredient_name or ingredient_name in user_ing 
                            for user_ing in user_ingredients
                        )
                    
                    # Count how many ingredients user has
                    has_count = sum(1 for ing in ingredients if ing.get('has_it'))
                    total_count = len(ingredients)
                    
                    # Format instructions (split into steps)
                    instructions = meal.get('strInstructions', '')
                    instruction_steps = []
                    if instructions:
                        # Split by newlines or numbers
                        steps = instructions.split('\r\n')
                        if len(steps) == 1:
                            steps = instructions.split('. ')
                        
                        for i, step in enumerate(steps, 1):
                            if step.strip():
                                instruction_steps.append({
                                    'number': i,
                                    'text': step.strip().strip('.')
                                })
                    
                    # Prepare recipe data
                    recipe_data = {
                        'id': meal.get('idMeal'),
                        'title': meal.get('strMeal', 'Unknown Recipe'),
                        'category': meal.get('strCategory', ''),
                        'area': meal.get('strArea', ''),
                        'instructions': instructions,
                        'instruction_steps': instruction_steps if instruction_steps else [{'number': 1, 'text': instructions}],
                        'image': meal.get('strMealThumb', ''),
                        'youtube': meal.get('strYoutube', ''),
                        'source': meal.get('strSource', ''),
                        'ingredients': ingredients,
                        'tags': meal.get('strTags', '').split(',') if meal.get('strTags') else [],
                        'has_count': has_count,
                        'total_count': total_count,
                        'ingredients_percentage': int((has_count / total_count * 100)) if total_count > 0 else 0,
                    }
                    
                    # Cache for 24 hours
                    cache.set(cache_key, recipe_data, 86400)
                    
                else:
                    recipe_data = {'error': 'Recipe not found'}
            else:
                recipe_data = {'error': 'API error'}
                
        except Exception as e:
            recipe_data = {'error': f'Error fetching recipe: {str(e)}'}
    
    context = {
        'page_title': recipe_data.get('title', 'Recipe Details') if isinstance(recipe_data, dict) else 'Recipe Details',
        'recipe': recipe_data if isinstance(recipe_data, dict) else {},
        'recipe_id': recipe_id,
    }
    return render(request, 'recipes/detail.html', context)