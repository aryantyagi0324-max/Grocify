"""
API utilities for TheMealDB integration.
FREE API - no API key required!
"""
import requests
import json
import random
from django.core.cache import cache
from django.conf import settings
from .indian_recipes import INDIAN_RECIPES
import re
import string
from datetime import date


def get_recipes_by_ingredients(ingredients, number=10):
    """
    Get recipes based on available ingredients using TheMealDB API
    """
    if not ingredients:
        return {
            'error': 'No ingredients provided',
            'recipes': []
        }
    
    # Create cache key based on ingredients
    ingredients_key = '_'.join(sorted([ing.lower().replace(' ', '_') for ing in ingredients[:3]]))
    cache_key = f"themealdb_recipes_{ingredients_key}_{number}"
    
    # Try to get from cache first
    cached = cache.get(cache_key)
    if cached:
        print(f"✅ Using cached TheMealDB recipes for: {ingredients[:3]}")
        cached['cached'] = True
        return cached
    
    print(f"🔄 Fetching fresh TheMealDB recipes for: {ingredients[:3]}")
    
    try:
        # TheMealDB doesn't have a direct "find by ingredients" endpoint
        # So we'll search by first ingredient and then filter
        primary_ingredient = ingredients[0] if ingredients else ''
        
        formatted_recipes = []
        
        if primary_ingredient:
            # Search by ingredient
            url = f"{settings.THEMEALDB_BASE_URL}/filter.php"
            params = {
                'i': primary_ingredient.lower()
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('meals'):
                    # Get detailed information for each recipe
                    recipe_ids = [meal['idMeal'] for meal in data['meals'][:min(number*2, 20)]]
                    
                    # Get details for each recipe
                    detailed_recipes = []
                    for recipe_id in recipe_ids:
                        details = get_recipe_details(recipe_id)
                        if details:
                            detailed_recipes.append(details)
                    
                    # Filter recipes that contain at least one of our ingredients
                    for recipe in detailed_recipes[:number]:
                        recipe_ingredients = extract_ingredients_from_meal(recipe)
                        recipe_ingredient_names = [ing['name'].lower() for ing in recipe_ingredients]
                        
                        # Check if recipe uses any of our ingredients
                        matches_ingredient = False
                        for user_ing in ingredients[:5]:
                            for recipe_ing in recipe_ingredient_names:
                                if _check_ingredient_match_smart(user_ing.lower(), recipe_ing):
                                    matches_ingredient = True
                                    break
                            if matches_ingredient:
                                break
                        
                        if matches_ingredient:
                            formatted_recipe = _format_recipe_themealdb(recipe, recipe_ingredients)
                            formatted_recipes.append(formatted_recipe)
        
        # If we don't have enough recipes, add random popular recipes
        if len(formatted_recipes) < min(number, 6):
            # Get random popular meals
            url = f"{settings.THEMEALDB_BASE_URL}/random.php"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('meals'):
                    for meal in data['meals'][:min(number - len(formatted_recipes), 5)]:
                        recipe_ingredients = extract_ingredients_from_meal(meal)
                        formatted_recipe = _format_recipe_themealdb(meal, recipe_ingredients)
                        formatted_recipes.append(formatted_recipe)
        
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
                    formatted_recipe = _format_indian_recipe(indian_recipe)
                    formatted_recipes.append(formatted_recipe)
        
        response = {
            'success': True,
            'recipes': formatted_recipes,
            'total_recipes': len(formatted_recipes),
            'ingredients_searched': ingredients[:3],
            'cached': False,
            'load_time': 'fresh',
            'api': 'themealdb'
        }
        
        # Cache for 6 hours
        cache.set(cache_key, response, 21600)
        
        return response
        
    except Exception as e:
        print(f"Error fetching TheMealDB recipes: {e}")
        # Return fallback Indian recipes on error
        if INDIAN_RECIPES:
            formatted_recipes = []
            for indian_recipe in INDIAN_RECIPES[:min(number, 8)]:
                formatted_recipe = _format_indian_recipe(indian_recipe)
                formatted_recipes.append(formatted_recipe)
            
            return {
                'success': True,
                'recipes': formatted_recipes,
                'total_recipes': len(formatted_recipes),
                'ingredients_searched': ingredients[:3],
                'cached': False,
                'load_time': 'error_fallback',
                'api': 'themealdb_fallback'
            }
        
        return {
            'error': str(e),
            'recipes': []
        }


def extract_ingredients_from_meal(meal):
    """Extract ingredients from TheMealDB recipe format"""
    ingredients = []
    
    for i in range(1, 21):  # TheMealDB has up to 20 ingredients
        ingredient_key = f'strIngredient{i}'
        measure_key = f'strMeasure{i}'
        
        ingredient = meal.get(ingredient_key, '').strip()
        measure = meal.get(measure_key, '').strip()
        
        if ingredient and ingredient.lower() != 'null' and ingredient.lower() != '':
            ingredients.append({
                'name': ingredient,
                'measure': measure,
                'display': f"{measure} {ingredient}".strip() if measure else ingredient
            })
    
    return ingredients


def _format_recipe_themealdb(meal, ingredients):
    """Format TheMealDB recipe data for template"""
    
    # Get instructions
    instructions = meal.get('strInstructions', '')
    
    # Parse instructions into steps
    instruction_steps = []
    if instructions:
        # Split by newlines or periods
        steps = []
        if '\r\n' in instructions:
            steps = [step.strip() for step in instructions.split('\r\n') if step.strip()]
        elif '\n' in instructions:
            steps = [step.strip() for step in instructions.split('\n') if step.strip()]
        else:
            # Split by sentences
            sentences = re.split(r'(?<=[.!?])\s+', instructions)
            steps = [s.strip() for s in sentences if s.strip()]
        
        # Create numbered steps
        for i, step in enumerate(steps[:15], 1):  # Limit to 15 steps
            instruction_steps.append({
                'number': i,
                'text': step
            })
    
    # Get category and area
    category = meal.get('strCategory', 'General')
    area = meal.get('strArea', 'International')
    
    # Determine if it's Indian
    is_indian = area.lower() == 'indian' or any(word in category.lower() for word in ['indian', 'curry'])
    
    # Get YouTube video if available
    youtube_url = meal.get('strYoutube', '')
    
    return {
        'id': meal.get('idMeal'),
        'title': meal.get('strMeal', 'Unknown Recipe'),
        'category': category,
        'image': meal.get('strMealThumb'),
        'instructions': instructions,
        'instruction_steps': instruction_steps,
        'short_instructions': instructions[:150] + '...' if instructions else 'No instructions available',
        'ingredients': ingredients,
        'ingredients_count': len(ingredients),
        'cooking_time': 30,  # TheMealDB doesn't provide cooking time, default to 30
        'servings': 4,  # Default servings
        'has_all_ingredients': False,
        'missing_ingredients': [],
        'tags': [meal.get('strTags', '')] if meal.get('strTags') else [],
        'source': meal.get('strSource', ''),
        'youtube': youtube_url,
        'area': area,
        'is_indian': is_indian,
        'api': 'themealdb'
    }


def _format_indian_recipe(indian_recipe):
    """Format Indian recipe data for template"""
    instruction_steps = []
    if indian_recipe.get('instructions'):
        instructions = indian_recipe['instructions']
        steps = instructions.split('. ')
        for i, step in enumerate(steps, 1):
            if step.strip():
                instruction_steps.append({
                    'number': i,
                    'text': step.strip() + ('.' if not step.endswith('.') else '')
                })
    
    return {
        'id': indian_recipe['id'],
        'title': indian_recipe['title'],
        'category': indian_recipe['category'],
        'image': indian_recipe['image'],
        'instructions': indian_recipe['instructions'],
        'instruction_steps': instruction_steps,
        'short_instructions': indian_recipe['short_instructions'],
        'ingredients': [{'name': ing['name'], 'measure': f"{ing['amount']} {ing['unit']}", 'display': f"{ing['amount']} {ing['unit']} {ing['name']}"} 
                       for ing in indian_recipe['ingredients']],
        'ingredients_count': len(indian_recipe['ingredients']),
        'cooking_time': indian_recipe['cooking_time'],
        'servings': indian_recipe['servings'],
        'has_all_ingredients': False,
        'missing_ingredients': [],
        'tags': indian_recipe['tags'],
        'source': '',
        'youtube': '',
        'area': 'Indian',
        'is_indian': True,
        'api': 'indian_fallback'
    }


def get_recipe_suggestions(user_items):
    """
    Get recipe suggestions based on user's inventory using TheMealDB
    """
    # Extract ingredient names
    ingredients = [item.name.lower() for item in user_items if item.name]
    
    if not ingredients:
        return {
            'error': 'No ingredients in inventory',
            'recipes': [],
            'cached': True,
            'api': 'themealdb'
        }
    
    # Clean and prepare ingredients
    cleaned_ingredients = []
    for ingredient in ingredients:
        # Clean the ingredient name
        ingredient_clean = ingredient.lower().strip()
        
        # Remove quantity indicators
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
        
        if ingredient_clean:
            cleaned_ingredients.append(ingredient_clean)
    
    # Remove duplicates
    unique_ingredients = list(set(cleaned_ingredients))
    
    # Limit ingredients for API call
    search_ingredients = unique_ingredients[:5]  # TheMealDB works better with fewer ingredients
    
    # Get recipe suggestions
    recipe_data = get_recipes_by_ingredients(search_ingredients, number=12)
    
    # Filter recipes to show only those where user has most ingredients
    if recipe_data.get('recipes'):
        user_ingredients_set = set(search_ingredients)
        scored_recipes = []
        
        for recipe in recipe_data['recipes']:
            # Calculate ingredient match score with smart matching
            recipe_ingredients = []
            if isinstance(recipe.get('ingredients'), list):
                recipe_ingredients = [ing.get('name', '').lower() 
                                     for ing in recipe['ingredients'] 
                                     if ing.get('name')]
            
            # Calculate match score
            match_score = 0
            total_ingredients = len(recipe_ingredients)
            
            if total_ingredients > 0:
                for recipe_ing in recipe_ingredients:
                    for user_ing in user_ingredients_set:
                        if _check_ingredient_match_smart(user_ing, recipe_ing):
                            match_score += 1
                            break
                
                recipe['match_percentage'] = int((match_score / total_ingredients) * 100) if total_ingredients > 0 else 0
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
    """Get detailed recipe information from TheMealDB"""
    # Check if it's a fallback Indian recipe ID
    if recipe_id.startswith('indian_'):
        # Find the Indian recipe
        for recipe in INDIAN_RECIPES:
            if recipe['id'] == recipe_id:
                return _format_indian_recipe_for_detail(recipe)
    
    cache_key = f"themealdb_details_{recipe_id}"
    cached = cache.get(cache_key)
    
    if cached:
        return cached
    
    try:
        url = f"{settings.THEMEALDB_BASE_URL}/lookup.php"
        params = {
            'i': recipe_id
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('meals'):
                meal = data['meals'][0]
                
                # Extract ingredients
                ingredients = extract_ingredients_from_meal(meal)
                
                # Get instructions
                instructions = meal.get('strInstructions', '')
                
                # Parse instructions into steps
                instruction_steps = []
                if instructions:
                    # Split by newlines or periods
                    steps = []
                    if '\r\n' in instructions:
                        steps = [step.strip() for step in instructions.split('\r\n') if step.strip()]
                    elif '\n' in instructions:
                        steps = [step.strip() for step in instructions.split('\n') if step.strip()]
                    else:
                        # Split by sentences
                        sentences = re.split(r'(?<=[.!?])\s+', instructions)
                        steps = [s.strip() for s in sentences if s.strip()]
                    
                    # Create numbered steps
                    for i, step in enumerate(steps[:15], 1):  # Limit to 15 steps
                        instruction_steps.append({
                            'number': i,
                            'text': step
                        })
                
                detailed_recipe = {
                    'id': meal.get('idMeal'),
                    'title': meal.get('strMeal'),
                    'image': meal.get('strMealThumb'),
                    'summary': f"A delicious {meal.get('strArea', '')} {meal.get('strCategory', 'recipe')}.",
                    'instructions': instructions,
                    'instruction_steps': instruction_steps,
                    'readyInMinutes': 30,  # TheMealDB doesn't provide cooking time
                    'servings': 4,  # Default servings
                    'sourceUrl': meal.get('strSource', ''),
                    'youtube': meal.get('strYoutube', ''),
                    'area': meal.get('strArea', ''),
                    'category': meal.get('strCategory', ''),
                    'tags': meal.get('strTags', '').split(',') if meal.get('strTags') else [],
                    'ingredients': ingredients,
                    'extendedIngredients': ingredients,  # For compatibility
                    'is_indian': meal.get('strArea', '').lower() == 'indian',
                    'api': 'themealdb'
                }
                
                cache.set(cache_key, detailed_recipe, 43200)
                return detailed_recipe
            
    except Exception as e:
        print(f"Error fetching recipe details {recipe_id}: {e}")
    
    return None


def _format_indian_recipe_for_detail(indian_recipe):
    """Format Indian recipe for detail view"""
    instruction_steps = []
    if indian_recipe.get('instructions'):
        instructions = indian_recipe['instructions']
        steps = instructions.split('. ')
        for i, step in enumerate(steps, 1):
            if step.strip():
                instruction_steps.append({
                    'number': i,
                    'text': step.strip() + ('.' if not step.endswith('.') else '')
                })
    
    ingredients = []
    for ing in indian_recipe['ingredients']:
        ingredients.append({
            'name': ing['name'],
            'measure': f"{ing['amount']} {ing['unit']}",
            'display': f"{ing['amount']} {ing['unit']} {ing['name']}",
            'original': f"{ing['amount']} {ing['unit']} {ing['name']}"
        })
    
    return {
        'id': indian_recipe['id'],
        'title': indian_recipe['title'],
        'image': indian_recipe['image'],
        'summary': f"A delicious Indian {indian_recipe['category'].lower()} recipe.",
        'instructions': indian_recipe['instructions'],
        'instruction_steps': instruction_steps,
        'readyInMinutes': indian_recipe['cooking_time'],
        'servings': indian_recipe['servings'],
        'sourceUrl': '',
        'youtube': '',
        'area': 'Indian',
        'category': indian_recipe['category'],
        'tags': indian_recipe['tags'],
        'ingredients': ingredients,
        'extendedIngredients': ingredients,
        'is_indian': True,
        'api': 'indian_fallback'
    }


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
        'rice': ['chawal'],
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