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
import re
import requests
from django.core.cache import cache
import random
import threading

# Helper functions for recipe instructions
def create_smart_instructions(meal, ingredients):
    """Create detailed cooking instructions from scratch"""
    steps = []
    step_num = 1
    
    # Get recipe info
    title = meal.get('strMeal', 'Recipe').lower()
    category = meal.get('strCategory', 'General').lower()
    area = meal.get('strArea', '').lower()
    
    # Step 1: Preparation
    prep_items = []
    for ing in ingredients[:8]:  # Limit to first 8 ingredients
        if ing['measure'].strip():
            prep_items.append(f"{ing['measure']} {ing['name']}")
        else:
            prep_items.append(ing['name'])
    
    if prep_items:
        steps.append({
            'number': step_num,
            'text': f"Gather and prepare your ingredients: {', '.join(prep_items[:5])}" + 
                   (f" and {len(prep_items) - 5} more items" if len(prep_items) > 5 else "")
        })
        step_num += 1
    
    # Step 2: Initial preparation based on category
    if 'chicken' in title or 'meat' in title or 'beef' in title or 'pork' in title:
        steps.append({
            'number': step_num,
            'text': f"Clean and pat dry the meat. Cut into bite-sized pieces if needed. Season with salt and pepper."
        })
        step_num += 1
    elif 'vegetable' in category or 'salad' in category or any(v in title for v in ['salad', 'vegetable', 'veggie']):
        steps.append({
            'number': step_num,
            'text': f"Wash all vegetables thoroughly. Chop, dice, or slice according to your preference."
        })
        step_num += 1
    elif 'dessert' in category or 'cake' in title or 'cookie' in title or 'pie' in title:
        steps.append({
            'number': step_num,
            'text': f"Preheat oven to 350°F (175°C). Grease baking dish or line with parchment paper."
        })
        step_num += 1
    
    # Step 3: Cooking method based on area/category
    cooking_methods = {
        'italian': "Heat olive oil in a large pan over medium heat",
        'mexican': "Heat oil in a skillet or comal over medium-high heat",
        'indian': "Heat ghee or oil in a kadai or deep pan over medium heat",
        'chinese': "Heat vegetable oil in a wok over high heat",
        'american': "Heat oil or butter in a large skillet over medium heat",
        'british': "Melt butter in a saucepan over medium heat",
        'japanese': "Prepare your cooking station with all ingredients within reach",
        'french': "Melt butter in a sauté pan over medium-low heat",
    }
    
    cooking_method = cooking_methods.get(area, "Heat oil in a pan over medium heat")
    steps.append({
        'number': step_num,
        'text': cooking_method + "."
    })
    step_num += 1
    
    # Step 4-6: Cooking steps
    cooking_steps = [
        "Add main ingredients and cook until they start to brown, about 5-7 minutes",
        "Add aromatic vegetables (like onions, garlic, ginger) and cook until fragrant, about 2-3 minutes",
        "Add any spices or seasonings and toast for 30 seconds to release their flavors",
        "Add liquid ingredients (broth, water, cream, tomatoes) and bring to a simmer",
        "Reduce heat to low, cover, and let cook for 15-20 minutes until everything is tender",
        "Taste and adjust seasoning with salt, pepper, or other spices as needed",
        "If the dish is too thin, let it simmer uncovered to reduce. If too thick, add a splash of water or broth",
        "Cook until all ingredients are tender and flavors are well combined"
    ]
    
    # Select appropriate cooking steps based on dish type
    if 'soup' in title or 'stew' in title or 'curry' in title:
        selected_steps = [0, 3, 4, 5, 6]  # Indexes for soup-like dishes
    elif 'stir' in title or 'fry' in title:
        selected_steps = [0, 1, 2, 7]  # Indexes for stir-fries
    elif 'bake' in title or 'roast' in title:
        selected_steps = [4, 5, 7]  # Indexes for baked dishes
    else:
        selected_steps = [0, 1, 2, 4, 5]  # Default selection
    
    for idx in selected_steps[:3]:  # Take first 3 selected steps
        steps.append({
            'number': step_num,
            'text': cooking_steps[idx] + "."
        })
        step_num += 1
    
    # Step 7: Finishing touches
    finishing_options = [
        "Garnish with fresh herbs before serving",
        "Drizzle with a finishing oil or sauce",
        "Serve with suggested accompaniments",
        "Let rest for 5 minutes before serving to allow flavors to meld",
        "Adjust consistency with additional liquid if needed"
    ]
    
    steps.append({
        'number': step_num,
        'text': random.choice(finishing_options) + "."
    })
    step_num += 1
    
    # Final step: Serving
    serving_options = [
        f"Serve hot, garnished with fresh herbs",
        f"Enjoy immediately while warm and fresh",
        f"Plate beautifully and serve with your favorite sides",
        f"Serve in individual bowls or on a large platter for sharing"
    ]
    
    steps.append({
        'number': step_num,
        'text': random.choice(serving_options) + "."
    })
    
    return steps

def parse_existing_instructions(instructions):
    """Parse existing instructions into proper steps"""
    steps = []
    
    if not instructions or len(instructions.strip()) < 10:
        return steps
    
    # Clean the instructions
    instructions = instructions.strip()
    
    # Try different splitting methods
    # Method 1: Split by numbered steps (1., 2., etc.)
    numbered_pattern = r'(\d+)[\.\)]\s*'
    if re.search(numbered_pattern, instructions):
        parts = re.split(numbered_pattern, instructions)
        step_num = 1
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                text = parts[i + 1].strip()
                if text:
                    # Clean up the text
                    text = re.sub(r'^\d+[\.\)]\s*', '', text)
                    text = text.strip()
                    
                    # Capitalize first letter
                    if text and not text[0].isupper():
                        text = text[0].upper() + text[1:]
                    
                    # Ensure it ends with punctuation
                    if text and not text[-1] in '.!?':
                        text += '.'
                    
                    steps.append({
                        'number': step_num,
                        'text': text
                    })
                    step_num += 1
    
    # Method 2: Split by line breaks
    if not steps and '\n' in instructions:
        lines = instructions.split('\n')
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if line and len(line) > 5:  # Skip very short lines
                # Clean the line
                line = re.sub(r'^\d+[\.\)]\s*', '', line)
                line = line.strip()
                
                if line:
                    # Capitalize first letter
                    if line and not line[0].isupper():
                        line = line[0].upper() + line[1:]
                    
                    # Ensure it ends with punctuation
                    if line and not line[-1] in '.!?':
                        line += '.'
                    
                    steps.append({
                        'number': i,
                        'text': line
                    })
    
    # Method 3: Split by sentences
    if not steps:
        # Split by sentence endings
        sentences = re.split(r'(?<=[.!?])\s+', instructions)
        for i, sentence in enumerate(sentences, 1):
            sentence = sentence.strip()
            if sentence and len(sentence.split()) > 3:  # Skip very short sentences
                # Clean the sentence
                sentence = re.sub(r'^\d+[\.\)]\s*', '', sentence)
                sentence = sentence.strip()
                
                if sentence:
                    # Capitalize first letter
                    if sentence and not sentence[0].isupper():
                        sentence = sentence[0].upper() + sentence[1:]
                    
                    steps.append({
                        'number': i,
                        'text': sentence
                    })
    
    # Limit to reasonable number of steps
    if len(steps) > 12:
        steps = steps[:12]
    
    return steps

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
        'expiring_items': expiring_items,
        'expired_items_list': expired_items_display,
        'expiry_summary': expiry_summary,
        'today': today,
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
    """Recipe suggestions page WITH performance optimizations"""
    user_items = FoodItem.objects.filter(user=request.user)
    
    # Get recipe suggestions (will use cache if available)
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
    # Check cache first
    cache_key = f"recipe_detail_full_{recipe_id}"
    recipe_data = cache.get(cache_key)
    
    if not recipe_data:
        # Fetch recipe details from TheMealDB API
        try:
            url = "https://www.themealdb.com/api/json/v1/1/lookup.php"
            params = {'i': recipe_id}
            
            response = requests.get(url, params=params, timeout=8)
            
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
                    
                    # NEW: Create proper cooking instructions
                    instructions = meal.get('strInstructions', '')
                    
                    # Try to parse existing instructions
                    parsed_steps = parse_existing_instructions(instructions)
                    
                    # If parsed instructions are good (at least 3 steps), use them
                    if len(parsed_steps) >= 3:
                        instruction_steps = parsed_steps
                    else:
                        # Generate smart instructions from scratch
                        instruction_steps = create_smart_instructions(meal, ingredients)
                    
                    # Prepare recipe data
                    recipe_data = {
                        'id': meal.get('idMeal'),
                        'title': meal.get('strMeal', 'Unknown Recipe'),
                        'category': meal.get('strCategory', ''),
                        'area': meal.get('strArea', ''),
                        'instructions': instructions,
                        'instruction_steps': instruction_steps,
                        'image': meal.get('strMealThumb', ''),
                        'youtube': meal.get('strYoutube', ''),
                        'source': meal.get('strSource', ''),
                        'ingredients': ingredients,
                        'tags': meal.get('strTags', '').split(',') if meal.get('strTags') else [],
                        'has_count': has_count,
                        'total_count': total_count,
                        'ingredients_percentage': int((has_count / total_count * 100)) if total_count > 0 else 0,
                        'cached': False
                    }
                    
                    # Cache for 24 hours
                    cache.set(cache_key, recipe_data, 86400)
                    
                else:
                    recipe_data = {'error': 'Recipe not found'}
            else:
                recipe_data = {'error': 'API error'}
                
        except Exception as e:
            recipe_data = {'error': f'Error fetching recipe: {str(e)}'}
    else:
        recipe_data['cached'] = True
    
    context = {
        'page_title': recipe_data.get('title', 'Recipe Details') if isinstance(recipe_data, dict) else 'Recipe Details',
        'recipe': recipe_data if isinstance(recipe_data, dict) else {},
        'recipe_id': recipe_id,
    }
    return render(request, 'recipes/detail.html', context)