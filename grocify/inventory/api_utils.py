import requests
import json
import random
from django.core.cache import cache
from django.conf import settings
import concurrent.futures
from datetime import date
import time
import re

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
                
                # Check if recipe contains any of our ingredients
                for user_ing in ingredients[:5]:  # Check against first 5 user ingredients
                    user_ing_lower = user_ing.lower()
                    if (any(user_ing_lower in ing for ing in recipe_ingredients) or 
                        any(user_ing_lower in ing for ing in recipe_ingredients_clean)):
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
            'id': ingredient.get('id')
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
    Prioritize recipes based on what user actually has
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
                           'piece', 'pieces', 'pc', 'pcs', 'cup', 'cups', 'tsp', 'tbsp', 'oz']
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
    recipe_data = get_recipes_by_ingredients(search_ingredients, number=12)
    
    # Filter recipes to show only those where user has most ingredients
    if recipe_data.get('recipes'):
        user_ingredients_set = set(search_ingredients)
        
        for recipe in recipe_data['recipes']:
            # Calculate ingredient match percentage
            recipe_ingredients = [ing['name'].lower() for ing in recipe['ingredients']]
            
            # Find matching ingredients (fuzzy match)
            matching_ingredients = 0
            for user_ing in user_ingredients_set:
                for recipe_ing in recipe_ingredients:
                    # Check if user ingredient is in recipe ingredient or vice versa
                    if (user_ing in recipe_ing or recipe_ing in user_ing or
                        any(word in recipe_ing for word in user_ing.split()) or
                        any(word in user_ing for word in recipe_ing.split())):
                        matching_ingredients += 1
                        break
            
            recipe['match_percentage'] = int((matching_ingredients / len(recipe_ingredients) * 100)) if recipe_ingredients else 0
            recipe['matching_ingredients'] = matching_ingredients
        
        # Sort by match percentage (highest first)
        recipe_data['recipes'].sort(key=lambda x: x['match_percentage'], reverse=True)
        # Keep only top matches
        recipe_data['recipes'] = recipe_data['recipes'][:8]
    
    return recipe_data

def get_recipe_details(recipe_id):
    """Get detailed recipe information from Spoonacular"""
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
                    'measures': ingredient.get('measures', {})
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

def check_ingredient_match(user_ingredient, recipe_ingredient):
    """
    Smart ingredient matching function
    Returns True if user has the ingredient (even if quantity differs)
    """
    user_ing = user_ingredient.lower()
    recipe_ing = recipe_ingredient.lower()
    
    # Remove quantities and measurements
    user_clean = re.sub(r'\d+\s*', '', user_ing)
    recipe_clean = re.sub(r'\d+\s*', '', recipe_ing)
    
    # Remove common measurement words
    measurement_words = ['kg', 'kgs', 'gram', 'grams', 'g', 'liter', 'liters', 'l', 'ml', 
                       'cup', 'cups', 'tsp', 'tbsp', 'oz', 'pound', 'pounds', 'lb', 'lbs',
                       'piece', 'pieces', 'pc', 'pcs', 'slice', 'slices', 'clove', 'cloves']
    
    for word in measurement_words:
        user_clean = re.sub(rf'\b{word}\b', '', user_clean)
        recipe_clean = re.sub(rf'\b{word}\b', '', recipe_clean)
    
    user_clean = user_clean.strip()
    recipe_clean = recipe_clean.strip()
    
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
    }
    
    # Check direct match
    if user_clean in recipe_clean or recipe_clean in user_clean:
        return True
    
    # Check synonym match
    for base_ing, syn_list in synonyms.items():
        if user_clean in syn_list and recipe_clean in syn_list:
            return True
        if user_clean == base_ing and recipe_clean in syn_list:
            return True
        if recipe_clean == base_ing and user_clean in syn_list:
            return True
    
    # Check word-by-word match
    user_words = set(user_clean.split())
    recipe_words = set(recipe_clean.split())
    
    if user_words.intersection(recipe_words):
        return True
    
    return False