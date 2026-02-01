import requests
import json
import random
from django.core.cache import cache
from django.conf import settings
from .indian_recipes import INDIAN_RECIPES
import concurrent.futures
from datetime import date
import time
import re
import string

def get_recipes_by_ingredients(ingredients, number=10):
    """
    Get recipes based on available ingredients using Spoonacular API
    Prioritize Indian recipes when possible
    """
    if not ingredients:
        return {
            'error': 'No ingredients provided',
            'recipes': []
        }
    
    # Create cache key based on ingredients
    ingredients_key = '_'.join(sorted([ing.lower().replace(' ', '_') for ing in ingredients[:3]]))
    cache_key = f"spoonacular_recipes_{ingredients_key}_{number}"
    
    # Try to get from cache first
    cached = cache.get(cache_key)
    if cached:
        print(f"✅ Using cached Spoonacular recipes for: {ingredients[:3]}")
        cached['cached'] = True
        return cached
    
    print(f"🔄 Fetching fresh Spoonacular recipes for: {ingredients[:3]}")
    
    # Prepare ingredients string for API call
    ingredients_str = ','.join(ingredients[:10])
    
    try:
        # First, try to find Indian recipes specifically
        indian_recipes = _search_indian_recipes_by_ingredients(ingredients, min(number, 6))
        
        # If we got enough Indian recipes, use them
        if len(indian_recipes) >= min(number, 4):
            formatted_recipes = [_format_recipe_spoonacular(recipe) for recipe in indian_recipes[:number]]
        else:
            # Get general recipes
            url = f"{settings.SPOONACULAR_BASE_URL}/recipes/findByIngredients"
            params = {
                'apiKey': settings.SPOONACULAR_API_KEY,
                'ingredients': ingredients_str,
                'number': number,
                'ranking': 2,  # Maximize used ingredients
                'ignorePantry': True,
                'limitLicense': False
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                recipes_data = response.json()
                
                # Get detailed information for each recipe
                recipe_ids = [recipe['id'] for recipe in recipes_data[:number]]
                
                if recipe_ids:
                    detailed_recipes = _get_bulk_recipe_info(recipe_ids)
                    # Prioritize Indian recipes if any
                    indian_recipes_in_results = [r for r in detailed_recipes if 'indian' in [c.lower() for c in r.get('cuisines', [])]]
                    other_recipes = [r for r in detailed_recipes if r not in indian_recipes_in_results]
                    
                    # Combine with our specifically searched Indian recipes
                    all_recipes = indian_recipes_in_results + other_recipes + indian_recipes
                    formatted_recipes = [_format_recipe_spoonacular(recipe) for recipe in all_recipes[:number]]
                else:
                    formatted_recipes = []
            else:
                formatted_recipes = []
        
        # FALLBACK: If no recipes found from API, use our Indian recipes
        if not formatted_recipes and INDIAN_RECIPES:
            print("⚠️ Using fallback Indian recipes")
            formatted_recipes = []
            for indian_recipe in INDIAN_RECIPES[:number]:
                # Check if user has any ingredients for this recipe
                recipe_ingredients = [ing['name'].lower() for ing in indian_recipe['ingredients']]
                user_has_any = any(_check_ingredient_match_smart(user_ing, recipe_ing) 
                                 for user_ing in ingredients[:5]
                                 for recipe_ing in recipe_ingredients)
                
                if user_has_any:
                    formatted_recipe = {
                        'id': indian_recipe['id'],
                        'title': indian_recipe['title'],
                        'category': indian_recipe['category'],
                        'image': indian_recipe['image'],
                        'instructions': indian_recipe['instructions'],
                        'instruction_steps': [],
                        'short_instructions': indian_recipe['short_instructions'],
                        'ingredients': [{'name': ing['name'], 'amount': ing['amount'], 'unit': ing['unit']} 
                                       for ing in indian_recipe['ingredients']],
                        'ingredients_count': len(indian_recipe['ingredients']),
                        'cooking_time': indian_recipe['cooking_time'],
                        'servings': indian_recipe['servings'],
                        'has_all_ingredients': False,
                        'missing_ingredients': [],
                        'tags': indian_recipe['tags'],
                        'source': '',
                        'spoonacular_score': 0,
                        'health_score': 0,
                        'price_per_serving': 0,
                        'very_popular': True,
                        'very_healthy': True,
                        'dairy_free': 'dairy' not in str(indian_recipe).lower(),
                        'gluten_free': 'gluten' not in str(indian_recipe).lower(),
                        'vegan': True,
                        'vegetarian': True,
                        'cuisines': ['Indian'],
                        'is_indian': True,
                        'api': 'spoonacular_fallback'
                    }
                    formatted_recipes.append(formatted_recipe)
        
        response = {
            'success': True,
            'recipes': formatted_recipes,
            'total_recipes': len(formatted_recipes),
            'ingredients_searched': ingredients[:3],
            'cached': False,
            'load_time': 'fresh',
            'api': 'spoonacular'
        }
        
        # Cache for 6 hours
        cache.set(cache_key, response, 21600)
        
        return response
        
    except Exception as e:
        print(f"Error fetching Spoonacular recipes: {e}")
        # Return fallback Indian recipes on error
        if INDIAN_RECIPES:
            formatted_recipes = []
            for indian_recipe in INDIAN_RECIPES[:min(number, 8)]:
                formatted_recipe = {
                    'id': indian_recipe['id'],
                    'title': indian_recipe['title'],
                    'category': indian_recipe['category'],
                    'image': indian_recipe['image'],
                    'instructions': indian_recipe['instructions'],
                    'instruction_steps': [],
                    'short_instructions': indian_recipe['short_instructions'],
                    'ingredients': [{'name': ing['name'], 'amount': ing['amount'], 'unit': ing['unit']} 
                                   for ing in indian_recipe['ingredients']],
                    'ingredients_count': len(indian_recipe['ingredients']),
                    'cooking_time': indian_recipe['cooking_time'],
                    'servings': indian_recipe['servings'],
                    'has_all_ingredients': False,
                    'missing_ingredients': [],
                    'tags': indian_recipe['tags'],
                    'source': '',
                    'spoonacular_score': 0,
                        'health_score': 0,
                        'price_per_serving': 0,
                        'very_popular': True,
                        'very_healthy': True,
                        'dairy_free': 'dairy' not in str(indian_recipe).lower(),
                        'gluten_free': 'gluten' not in str(indian_recipe).lower(),
                        'vegan': True,
                        'vegetarian': True,
                        'cuisines': ['Indian'],
                        'is_indian': True,
                        'api': 'spoonacular_fallback_error'
                    }
                formatted_recipes.append(formatted_recipe)
            
            return {
                'success': True,
                'recipes': formatted_recipes,
                'total_recipes': len(formatted_recipes),
                'ingredients_searched': ingredients[:3],
                'cached': False,
                'load_time': 'error_fallback',
                'api': 'spoonacular_fallback'
            }
        
        return {
            'error': str(e),
            'recipes': []
        }

def _search_indian_recipes_by_ingredients(ingredients, number=5):
    """Specifically search for Indian recipes with given ingredients"""
    if not ingredients:
        return []
    
    cache_key = f"spoonacular_indian_{'_'.join([ing.lower().replace(' ', '_') for ing in ingredients[:3]])}"
    cached = cache.get(cache_key)
    
    if cached:
        return cached
    
    try:
        # Search for Indian recipes
        url = f"{settings.SPOONACULAR_BASE_URL}/recipes/complexSearch"
        params = {
            'apiKey': settings.SPOONACULAR_API_KEY,
            'cuisine': 'indian',
            'number': number * 2,  # Get more to filter
            'addRecipeInformation': True,
            'fillIngredients': True,
            'sort': 'popularity',
            'sortDirection': 'desc'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            all_recipes = data.get('results', [])
            
            # Filter recipes that use at least one of our ingredients
            filtered_recipes = []
            for recipe in all_recipes:
                recipe_ingredients = [ing['name'].lower() for ing in recipe.get('extendedIngredients', [])]
                recipe_ingredients_clean = [ing['nameClean'].lower() for ing in recipe.get('extendedIngredients', []) if ing.get('nameClean')]
                
                # Check if recipe contains any of our ingredients using smart matching
                for user_ing in ingredients[:5]:  # Check against first 5 user ingredients
                    user_ing_lower = user_ing.lower()
                    if (any(_check_ingredient_match_smart(user_ing_lower, ing) for ing in recipe_ingredients) or 
                        any(_check_ingredient_match_smart(user_ing_lower, ing) for ing in recipe_ingredients_clean)):
                        filtered_recipes.append(recipe)
                        break
            
            cache.set(cache_key, filtered_recipes[:number], 21600)
            return filtered_recipes[:number]
            
    except Exception as e:
        print(f"Error searching Indian recipes: {e}")
    
    return []

def _get_bulk_recipe_info(recipe_ids):
    """Get bulk recipe information to minimize API calls"""
    if not recipe_ids:
        return []
    
    cache_key = f"spoonacular_bulk_{'_'.join(map(str, recipe_ids))}"
    cached = cache.get(cache_key)
    
    if cached:
        return cached
    
    try:
        # Spoonacular bulk endpoint
        url = f"{settings.SPOONACULAR_BASE_URL}/recipes/informationBulk"
        params = {
            'apiKey': settings.SPOONACULAR_API_KEY,
            'ids': ','.join(map(str, recipe_ids[:20]))
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            recipes = response.json()
            cache.set(cache_key, recipes, 21600)
            return recipes
        else:
            print(f"Bulk API error: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Error fetching bulk recipes: {e}")
        return []

def _format_recipe_spoonacular(recipe):
    """Format Spoonacular recipe data for template"""
    
    # Extract ingredients
    ingredient_list = []
    for ingredient in recipe.get('extendedIngredients', []):
        measure = ingredient.get('measures', {}).get('us', {}).get('amount', '')
        unit = ingredient.get('measures', {}).get('us', {}).get('unitShort', '')
        
        display_text = ""
        if measure:
            if isinstance(measure, float):
                # Simplify fractions
                if measure == int(measure):
                    measure = int(measure)
                else:
                    # Convert to fractions for common values
                    common_fractions = {
                        0.25: '¼', 0.33: '⅓', 0.5: '½', 0.66: '⅔', 0.75: '¾',
                        0.125: '⅛', 0.375: '⅜', 0.625: '⅝', 0.875: '⅞'
                    }
                    measure = common_fractions.get(measure, f"{measure:.2f}")
            display_text = f"{measure} {unit} {ingredient['nameClean'] or ingredient['name']}".strip()
        else:
            display_text = ingredient['nameClean'] or ingredient['name']
        
        ingredient_list.append({
            'display': display_text,
            'name': ingredient['nameClean'] or ingredient['name'],
            'original': ingredient.get('original', ''),
            'amount': ingredient.get('amount'),
            'unit': ingredient.get('unit'),
            'id': ingredient.get('id'),
            'nameClean': ingredient.get('nameClean', '').lower()
        })
    
    # Get cooking time
    cooking_time = recipe.get('readyInMinutes', 30)
    
    # Get instructions
    instructions = ""
    instruction_steps = []
    if recipe.get('analyzedInstructions') and len(recipe['analyzedInstructions']) > 0:
        steps = recipe['analyzedInstructions'][0].get('steps', [])
        instructions = ' '.join([step['step'] for step in steps])
        instruction_steps = [{'number': step['number'], 'text': step['step']} for step in steps]
    
    # Get dish types and diets
    dish_types = recipe.get('dishTypes', [])
    diets = recipe.get('diets', [])
    cuisines = recipe.get('cuisines', [])
    
    # Check if it's Indian cuisine
    is_indian = any('indian' in cuisine.lower() for cuisine in cuisines)
    if is_indian and 'indian' not in dish_types:
        dish_types.append('Indian')
    
    return {
        'id': recipe.get('id'),
        'title': recipe.get('title', 'Unknown Recipe'),
        'category': dish_types[0] if dish_types else 'General',
        'image': recipe.get('image'),
        'instructions': instructions,
        'instruction_steps': instruction_steps,
        'short_instructions': instructions[:150] + '...' if instructions else 'No instructions available',
        'ingredients': ingredient_list,  # Now a list of dictionaries
        'ingredients_count': len(ingredient_list),
        'cooking_time': cooking_time,
        'servings': recipe.get('servings', 4),
        'has_all_ingredients': False,
        'missing_ingredients': [],
        'tags': dish_types + diets + cuisines,
        'source': recipe.get('sourceUrl'),
        'spoonacular_score': recipe.get('spoonacularScore', 0),
        'health_score': recipe.get('healthScore', 0),
        'price_per_serving': recipe.get('pricePerServing', 0),
        'very_popular': recipe.get('veryPopular', False),
        'very_healthy': recipe.get('veryHealthy', False),
        'dairy_free': recipe.get('dairyFree', False),
        'gluten_free': recipe.get('glutenFree', False),
        'vegan': recipe.get('vegan', False),
        'vegetarian': recipe.get('vegetarian', False),
        'cuisines': cuisines,
        'is_indian': is_indian,
        'api': 'spoonacular'
    }

def get_recipe_suggestions(user_items):
    """
    Get recipe suggestions based on user's inventory using Spoonacular
    Prioritize recipes based on what user actually has with smart matching
    """
    # Extract ingredient names
    ingredients = [item.name.lower() for item in user_items if item.name]
    
    # Enhanced ingredient mappings for better Indian recipe matching
    ingredient_mappings = {
        # Dairy
        'milk': 'milk',
        'yogurt': 'yogurt',
        'curd': 'yogurt',
        'dahi': 'yogurt',
        'cheese': 'cheese',
        'paneer': 'paneer',
        'butter': 'butter',
        'ghee': 'ghee',
        'cream': 'cream',
        
        # Proteins
        'egg': 'eggs',
        'chicken': 'chicken',
        'mutton': 'lamb',
        'lamb': 'lamb',
        'fish': 'fish',
        'prawn': 'shrimp',
        'shrimp': 'shrimp',
        
        # Vegetables
        'onion': 'onion',
        'garlic': 'garlic',
        'ginger': 'ginger',
        'tomato': 'tomatoes',
        'potato': 'potatoes',
        'aloo': 'potatoes',
        'carrot': 'carrots',
        'gajar': 'carrots',
        'cauliflower': 'cauliflower',
        'gobhi': 'cauliflower',
        'spinach': 'spinach',
        'palak': 'spinach',
        'eggplant': 'eggplant',
        'baingan': 'eggplant',
        'brinjal': 'eggplant',
        'okra': 'okra',
        'bhindi': 'okra',
        'beans': 'green beans',
        'cabbage': 'cabbage',
        'peas': 'peas',
        'matar': 'peas',
        
        # Lentils & Grains
        'rice': 'rice',
        'chawal': 'rice',
        'wheat': 'wheat',
        'gehun': 'wheat',
        'lentil': 'lentils',
        'dal': 'lentils',
        'chickpea': 'chickpeas',
        'chana': 'chickpeas',
        'flour': 'flour',
        'atta': 'flour',
        'besan': 'gram flour',
        
        # Spices
        'turmeric': 'turmeric',
        'haldi': 'turmeric',
        'cumin': 'cumin',
        'jeera': 'cumin',
        'coriander': 'coriander',
        'dhania': 'coriander',
        'mustard': 'mustard seeds',
        'rai': 'mustard seeds',
        'chili': 'chili powder',
        'mirch': 'chili powder',
        'garam masala': 'garam masala',
        'cardamom': 'cardamom',
        'elaichi': 'cardamom',
        'cinnamon': 'cinnamon',
        'dalchini': 'cinnamon',
        'clove': 'cloves',
        'laung': 'cloves',
        'pepper': 'black pepper',
        'kali mirch': 'black pepper',
        
        # Basic
        'salt': 'salt',
        'namak': 'salt',
        'sugar': 'sugar',
        'chinni': 'sugar',
        'oil': 'oil',
        'tel': 'oil',
        
        # Fruits
        'lemon': 'lemon',
        'nimbu': 'lemon',
        'mango': 'mango',
        'aam': 'mango',
        'banana': 'banana',
        'kela': 'banana',
    }
    
    # Map ingredients to common names
    mapped_ingredients = []
    for ingredient in ingredients:
        # Clean the ingredient name
        ingredient_clean = ingredient.lower().strip()
        
        # Remove quantity indicators (e.g., "3 eggs" → "eggs")
        ingredient_clean = re.sub(r'\d+\s*', '', ingredient_clean)
        
        # Remove common measurement words
        measurement_words = ['kg', 'kgs', 'gram', 'grams', 'g', 'liter', 'liters', 'l', 'ml', 
                           'cup', 'cups', 'tsp', 'tbsp', 'oz', 'pound', 'pounds', 'lb', 'lbs',
                           'piece', 'pieces', 'pc', 'pcs', 'slice', 'slices', 'clove', 'cloves',
                           'bunch', 'bunches', 'pack', 'packs', 'bottle', 'bottles', 'can', 'cans',
                           'jar', 'jars', 'packet', 'packets', 'box', 'boxes']
        for word in measurement_words:
            ingredient_clean = re.sub(rf'\b{word}\b', '', ingredient_clean)
        
        ingredient_clean = ingredient_clean.strip()
        
        # Map to standardized name
        mapped = ingredient_mappings.get(ingredient_clean, ingredient_clean)
        
        # Remove trailing 's' for plural
        if mapped.endswith('s') and len(mapped) > 3:
            mapped = mapped[:-1]
        
        mapped_ingredients.append(mapped)
    
    # Remove duplicates
    unique_ingredients = list(set(mapped_ingredients))
    
    # Add common Indian ingredients if user has basics
    if any(ing in unique_ingredients for ing in ['onion', 'tomato', 'garlic', 'ginger']):
        if 'garam masala' not in unique_ingredients:
            unique_ingredients.append('garam masala')
        if 'turmeric' not in unique_ingredients:
            unique_ingredients.append('turmeric')
        if 'cumin' not in unique_ingredients:
            unique_ingredients.append('cumin')
    
    # Limit ingredients for API call
    search_ingredients = unique_ingredients[:10]
    
    if not search_ingredients:
        return {
            'error': 'No ingredients in inventory',
            'recipes': [],
            'cached': True,
            'api': 'spoonacular'
        }
    
    # Use Spoonacular API - get more recipes to filter
    recipe_data = get_recipes_by_ingredients(search_ingredients, number=15)
    
    # Filter recipes to show only those where user has most ingredients
    if recipe_data.get('recipes'):
        user_ingredients_set = set(search_ingredients)
        scored_recipes = []
        
        for recipe in recipe_data['recipes']:
            # Calculate ingredient match score with smart matching
            recipe_ingredients = []
            if isinstance(recipe.get('ingredients'), list):
                recipe_ingredients = [ing.get('nameClean', ing.get('name', '')).lower() 
                                     for ing in recipe['ingredients'] 
                                     if ing.get('nameClean') or ing.get('name')]
            
            # Calculate match score
            match_score = 0
            total_ingredients = len(recipe_ingredients)
            
            if total_ingredients > 0:
                for recipe_ing in recipe_ingredients:
                    for user_ing in user_ingredients_set:
                        if _check_ingredient_match_smart(user_ing, recipe_ing):
                            match_score += 1
                            break
                
                recipe['match_percentage'] = int((match_score / total_ingredients) * 100)
                recipe['matching_ingredients'] = match_score
                recipe['total_recipe_ingredients'] = total_ingredients
                
                # Add to scored recipes
                scored_recipes.append(recipe)
        
        # Sort by match percentage (highest first)
        scored_recipes.sort(key=lambda x: x['match_percentage'], reverse=True)
        
        # Filter out recipes with very low match percentage (< 20%)
        filtered_recipes = [r for r in scored_recipes if r['match_percentage'] >= 20]
        
        # If we have filtered recipes, use them
        if filtered_recipes:
            recipe_data['recipes'] = filtered_recipes[:10]
        else:
            # If no good matches, show top recipes anyway
            recipe_data['recipes'] = scored_recipes[:8]
    
    return recipe_data

def get_recipe_details(recipe_id):
    """Get detailed recipe information from Spoonacular"""
    # Check if it's a fallback Indian recipe ID
    if recipe_id.startswith('indian_'):
        # Find the Indian recipe
        for recipe in INDIAN_RECIPES:
            if recipe['id'] == recipe_id:
                # Convert to Spoonacular format
                instruction_steps = []
                if recipe.get('instructions'):
                    # Parse instructions into steps
                    instructions = recipe['instructions']
                    steps = instructions.split('. ')
                    for i, step in enumerate(steps, 1):
                        if step.strip():
                            instruction_steps.append({
                                'number': i,
                                'text': step.strip() + ('.' if not step.endswith('.') else '')
                            })
                
                return {
                    'id': recipe['id'],
                    'title': recipe['title'],
                    'image': recipe['image'],
                    'summary': f"A delicious Indian {recipe['category'].lower()} recipe.",
                    'instructions': recipe['instructions'],
                    'instruction_steps': instruction_steps,
                    'readyInMinutes': recipe['cooking_time'],
                    'servings': recipe['servings'],
                    'sourceUrl': '',
                    'spoonacularSourceUrl': '',
                    'healthScore': 75,
                    'pricePerServing': 2.50,
                    'dishTypes': [recipe['category']],
                    'diets': ['Vegetarian', 'Vegan'] if 'Vegetarian' in recipe['tags'] else ['Vegetarian'],
                    'cuisines': ['Indian'],
                    'ingredients': [{'name': ing['name'], 'amount': ing['amount'], 'unit': ing['unit']} 
                                   for ing in recipe['ingredients']],
                    'extendedIngredients': [{'name': ing['name'], 'amount': ing['amount'], 'unit': ing['unit']} 
                                           for ing in recipe['ingredients']],
                    'veryPopular': True,
                    'veryHealthy': True,
                    'dairyFree': 'dairy' not in str(recipe).lower(),
                    'glutenFree': 'gluten' not in str(recipe).lower(),
                    'vegan': 'Vegan' in recipe['tags'],
                    'vegetarian': 'Vegetarian' in recipe['tags'],
                    'api': 'spoonacular_fallback'
                }
    
    cache_key = f"spoonacular_details_{recipe_id}"
    cached = cache.get(cache_key)
    
    if cached:
        return cached
    
    try:
        url = f"{settings.SPOONACULAR_BASE_URL}/recipes/{recipe_id}/information"
        params = {
            'apiKey': settings.SPOONACULAR_API_KEY,
            'includeNutrition': False
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            recipe = response.json()
            
            # Format instructions
            instruction_steps = []
            if recipe.get('analyzedInstructions') and len(recipe['analyzedInstructions']) > 0:
                steps = recipe['analyzedInstructions'][0].get('steps', [])
                for step in steps:
                    instruction_steps.append({
                        'number': step['number'],
                        'text': step['step']
                    })
            
            # Format ingredients as list of dictionaries
            ingredients = []
            for ingredient in recipe.get('extendedIngredients', []):
                ingredients.append({
                    'id': ingredient.get('id'),
                    'name': ingredient.get('nameClean') or ingredient.get('name'),
                    'original': ingredient.get('original'),
                    'amount': ingredient.get('amount'),
                    'unit': ingredient.get('unit'),
                    'measures': ingredient.get('measures', {}),
                    'nameClean': ingredient.get('nameClean', '').lower()
                })
            
            detailed_recipe = {
                'id': recipe.get('id'),
                'title': recipe.get('title'),
                'image': recipe.get('image'),
                'summary': recipe.get('summary', ''),
                'instructions': recipe.get('instructions', ''),
                'instruction_steps': instruction_steps,
                'readyInMinutes': recipe.get('readyInMinutes', 30),
                'servings': recipe.get('servings', 4),
                'sourceUrl': recipe.get('sourceUrl'),
                'spoonacularSourceUrl': recipe.get('spoonacularSourceUrl'),
                'healthScore': recipe.get('healthScore', 0),
                'pricePerServing': recipe.get('pricePerServing', 0),
                'dishTypes': recipe.get('dishTypes', []),
                'diets': recipe.get('diets', []),
                'cuisines': recipe.get('cuisines', []),
                'ingredients': ingredients,
                'extendedIngredients': recipe.get('extendedIngredients', []),
                'veryPopular': recipe.get('veryPopular', False),
                'veryHealthy': recipe.get('veryHealthy', False),
                'dairyFree': recipe.get('dairyFree', False),
                'glutenFree': recipe.get('glutenFree', False),
                'vegan': recipe.get('vegan', False),
                'vegetarian': recipe.get('vegetarian', False),
                'api': 'spoonacular'
            }
            
            cache.set(cache_key, detailed_recipe, 43200)
            return detailed_recipe
            
    except Exception as e:
        print(f"Error fetching recipe details {recipe_id}: {e}")
    
    return None

def _check_ingredient_match_smart(user_ingredient, recipe_ingredient):
    """
    SMART ingredient matching function
    Returns True only if user has the EXACT or very similar ingredient
    """
    if not user_ingredient or not recipe_ingredient:
        return False
    
    user_ing = user_ingredient.lower().strip()
    recipe_ing = recipe_ingredient.lower().strip()
    
    # Remove punctuation
    user_ing = user_ing.translate(str.maketrans('', '', string.punctuation))
    recipe_ing = recipe_ing.translate(str.maketrans('', '', string.punctuation))
    
    # Remove common filler words
    filler_words = ['fresh', 'dried', 'powdered', 'ground', 'chopped', 'sliced', 'diced', 
                   'minced', 'grated', 'crushed', 'whole', 'raw', 'cooked', 'roasted',
                   'toasted', 'optional', 'for garnish', 'as needed', 'to taste']
    
    for word in filler_words:
        user_ing = re.sub(rf'\b{word}\b', '', user_ing)
        recipe_ing = re.sub(rf'\b{word}\b', '', recipe_ing)
    
    user_ing = user_ing.strip()
    recipe_ing = recipe_ing.strip()
    
    # Check for exact match
    if user_ing == recipe_ing:
        return True
    
    # Check if one is contained in the other (but not partial word matches)
    # This prevents "milk" matching "coconut milk"
    if user_ing in recipe_ing:
        # Check if it's a whole word match, not partial
        words = recipe_ing.split()
        if user_ing in words:
            return True
        # Check if user_ing is at the end (like "coconut milk" has "milk" at end)
        if recipe_ing.endswith(user_ing) and recipe_ing[-len(user_ing)-1] == ' ':
            return True
    
    if recipe_ing in user_ing:
        words = user_ing.split()
        if recipe_ing in words:
            return True
        if user_ing.endswith(recipe_ing) and user_ing[-len(recipe_ing)-1] == ' ':
            return True
    
    # Common ingredient synonyms for Indian cooking
    synonyms = {
        'egg': ['eggs', 'anda', 'andey'],
        'onion': ['onions', 'pyaz', 'pyaaz'],
        'tomato': ['tomatoes', 'tamatar'],
        'potato': ['potatoes', 'aloo', 'aaloo'],
        'garlic': ['lehsun', 'lasan'],
        'ginger': ['adrak'],
        'yogurt': ['curd', 'dahi', 'yoghurt'],
        'oil': ['tel', 'cooking oil'],
        'salt': ['namak'],
        'sugar': ['chinni', 'chini', 'shakkar'],
        'rice': ['chawal', 'chawal'],
        'wheat': ['gehun', 'atta'],
        'lentil': ['dal', 'daal', 'lentils'],
        'chickpea': ['chana', 'chhole', 'chickpeas'],
        'spinach': ['palak'],
        'cauliflower': ['gobhi', 'phoolgobhi'],
        'eggplant': ['baingan', 'brinjal', 'aubergine'],
        'okra': ['bhindi', 'lady finger'],
        'turmeric': ['haldi'],
        'cumin': ['jeera'],
        'coriander': ['dhania', 'coriander leaves', 'cilantro'],
        'mustard': ['rai', 'mustard seeds'],
        'chili': ['mirch', 'chilli', 'red chili'],
        'cardamom': ['elaichi'],
        'cinnamon': ['dalchini'],
        'clove': ['laung'],
        'milk': ['doodh'],
        'butter': ['makkhan'],
        'paneer': ['cottage cheese'],
        'cream': ['malai'],
        'flour': ['maida'],
        'gram flour': ['besan'],
        'fenugreek': ['methi'],
        'asafoetida': ['hing'],
        'tamarind': ['imli'],
        'jaggery': ['gur'],
    }
    
    # Check synonym match
    for base_ing, syn_list in synonyms.items():
        if user_ing in syn_list and recipe_ing in syn_list:
            return True
        if user_ing == base_ing and recipe_ing in syn_list:
            return True
        if recipe_ing == base_ing and user_ing in syn_list:
            return True
    
    # Check word-by-word match for multi-word ingredients
    user_words = set(user_ing.split())
    recipe_words = set(recipe_ing.split())
    
    common_words = user_words.intersection(recipe_words)
    if common_words:
        # Only return true if common words are significant (not filler)
        significant_words = [w for w in common_words if len(w) > 2 and w not in filler_words]
        if significant_words:
            return True
    
    # Special case: prevent "milk" matching "coconut milk" or "almond milk"
    if user_ing == 'milk':
        if 'coconut' in recipe_ing or 'almond' in recipe_ing or 'soy' in recipe_ing or 'oat' in recipe_ing:
            return False
        if recipe_ing.endswith(' milk') and recipe_ing != 'milk':
            return False
    
    # Special case: prevent "flour" matching specific flours
    if user_ing == 'flour':
        if 'wheat' in recipe_ing or 'rice' in recipe_ing or 'gram' in recipe_ing or 'all purpose' in recipe_ing:
            return False
    
    return False

def check_ingredient_match(user_ingredient, recipe_ingredient):
    """
    Wrapper function for backward compatibility
    Uses the new smart matching
    """
    return _check_ingredient_match_smart(user_ingredient, recipe_ingredient)