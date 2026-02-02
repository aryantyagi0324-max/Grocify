"""
API utilities for Spoonacular integration.
"""
import requests
import json
from django.core.cache import cache
from django.conf import settings
from .indian_recipes import INDIAN_RECIPES
import re
import string
from datetime import date


def get_recipes_by_ingredients(ingredients, number=10):
    """
    Get recipes based on available ingredients using Spoonacular API
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
    
    try:
        # Spoonacular API endpoint for finding recipes by ingredients
        url = f"{settings.SPOONACULAR_BASE_URL}/recipes/findByIngredients"
        
        params = {
            'apiKey': settings.SPOONACULAR_API_KEY,
            'ingredients': ','.join(ingredients[:5]),  # Use up to 5 ingredients
            'number': number,
            'ranking': 2,  # Maximize used ingredients
            'ignorePantry': True,  # Ignore pantry staples
            'limitLicense': False
        }
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            recipes_data = response.json()
            formatted_recipes = []
            
            for recipe_data in recipes_data:
                # Get detailed information for each recipe
                detailed_recipe = get_recipe_details(recipe_data['id'])
                if detailed_recipe:
                    formatted_recipe = _format_recipe_spoonacular(detailed_recipe, recipe_data)
                    formatted_recipes.append(formatted_recipe)
            
            # If we have formatted recipes, return them
            if formatted_recipes:
                response_data = {
                    'success': True,
                    'recipes': formatted_recipes,
                    'total_recipes': len(formatted_recipes),
                    'ingredients_searched': ingredients[:3],
                    'cached': False,
                    'load_time': 'fresh',
                    'api': 'spoonacular'
                }
                
                # Cache for 4 hours
                cache.set(cache_key, response_data, 14400)
                
                return response_data
        
        # If Spoonacular API fails or returns no results, use Indian recipes fallback
        print("⚠️ Spoonacular API returned no results, using Indian recipes fallback")
        return get_indian_recipes_fallback(ingredients, number)
        
    except Exception as e:
        print(f"Error fetching Spoonacular recipes: {e}")
        # Return fallback Indian recipes on error
        return get_indian_recipes_fallback(ingredients, number)


def get_indian_recipes_fallback(ingredients, number=10):
    """Fallback to Indian recipes when Spoonacular fails"""
    if INDIAN_RECIPES:
        formatted_recipes = []
        for indian_recipe in INDIAN_RECIPES[:number]:
            # Check if user has any ingredients for this recipe
            recipe_ingredients = [ing['name'].lower() for ing in indian_recipe['ingredients']]
            user_has_any = any(_check_ingredient_match_smart(user_ing, recipe_ing) 
                             for user_ing in ingredients[:5]
                             for recipe_ing in recipe_ingredients)
            
            if user_has_any or not ingredients:  # Show some recipes even if no match
                formatted_recipe = _format_indian_recipe(indian_recipe)
                formatted_recipes.append(formatted_recipe)
        
        return {
            'success': True,
            'recipes': formatted_recipes,
            'total_recipes': len(formatted_recipes),
            'ingredients_searched': ingredients[:3],
            'cached': False,
            'load_time': 'fallback',
            'api': 'indian_fallback'
        }
    
    return {
        'error': 'No recipes available',
        'recipes': []
    }


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
        
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            recipe_data = response.json()
            
            # Cache for 6 hours
            cache.set(cache_key, recipe_data, 21600)
            return recipe_data
            
    except Exception as e:
        print(f"Error fetching recipe details {recipe_id}: {e}")
    
    return None


def get_recipe_suggestions(user_items):
    """
    Get recipe suggestions based on user's inventory using Spoonacular
    """
    # Extract ingredient names
    ingredients = [item.name.lower() for item in user_items if item.name]
    
    if not ingredients:
        return {
            'error': 'No ingredients in inventory',
            'recipes': [],
            'cached': True,
            'api': 'spoonacular'
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
    
    # Get recipe suggestions
    recipe_data = get_recipes_by_ingredients(unique_ingredients, number=12)
    
    # Calculate match percentages for Spoonacular recipes
    if recipe_data.get('recipes'):
        for recipe in recipe_data['recipes']:
            if 'usedIngredients' in recipe and 'missedIngredients' in recipe:
                used_count = len(recipe.get('usedIngredients', []))
                missed_count = len(recipe.get('missedIngredients', []))
                total_ingredients = used_count + missed_count
                
                if total_ingredients > 0:
                    match_percentage = int((used_count / total_ingredients) * 100)
                    recipe['match_percentage'] = match_percentage
                    recipe['matching_ingredients'] = used_count
                    recipe['total_recipe_ingredients'] = total_ingredients
                    
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
    
    return recipe_data


def _format_recipe_spoonacular(detailed_recipe, summary_data):
    """Format Spoonacular recipe data for template"""
    
    # Extract instructions
    instruction_steps = []
    if detailed_recipe.get('analyzedInstructions') and len(detailed_recipe['analyzedInstructions']) > 0:
        for instruction in detailed_recipe['analyzedInstructions'][0]['steps']:
            instruction_steps.append({
                'number': instruction['number'],
                'text': instruction['step']
            })
    
    # Get used and missed ingredients from summary data
    used_ingredients = []
    missed_ingredients = []
    
    if 'usedIngredients' in summary_data:
        used_ingredients = [
            {
                'name': ing['name'],
                'amount': ing['amount'],
                'unit': ing['unit'],
                'original': f"{ing['amount']} {ing['unit']} {ing['name']}"
            }
            for ing in summary_data['usedIngredients']
        ]
    
    if 'missedIngredients' in summary_data:
        missed_ingredients = [
            {
                'name': ing['name'],
                'amount': ing['amount'],
                'unit': ing['unit'],
                'original': f"{ing['amount']} {ing['unit']} {ing['name']}"
            }
            for ing in summary_data['missedIngredients']
        ]
    
    # Combine all ingredients
    all_ingredients = used_ingredients + missed_ingredients
    
    # Check if it's Indian cuisine
    is_indian = False
    if detailed_recipe.get('cuisines'):
        is_indian = any('indian' in cuisine.lower() for cuisine in detailed_recipe['cuisines'])
    
    return {
        'id': detailed_recipe.get('id'),
        'title': detailed_recipe.get('title', 'Unknown Recipe'),
        'category': ', '.join(detailed_recipe.get('dishTypes', []))[:50] or 'General',
        'image': detailed_recipe.get('image'),
        'summary': detailed_recipe.get('summary', ''),
        'instructions': detailed_recipe.get('instructions', ''),
        'instruction_steps': instruction_steps,
        'short_instructions': (detailed_recipe.get('summary') or '')[:150] + '...',
        'ingredients': all_ingredients,
        'usedIngredients': used_ingredients,
        'missedIngredients': missed_ingredients,
        'ingredients_count': len(all_ingredients),
        'cooking_time': detailed_recipe.get('readyInMinutes', 30),
        'servings': detailed_recipe.get('servings', 4),
        'has_all_ingredients': len(missed_ingredients) == 0,
        'missing_ingredients': missed_ingredients,
        'tags': detailed_recipe.get('dishTypes', []) + detailed_recipe.get('diets', []),
        'sourceUrl': detailed_recipe.get('sourceUrl', ''),
        'spoonacularSourceUrl': detailed_recipe.get('spoonacularSourceUrl', ''),
        'healthScore': detailed_recipe.get('healthScore'),
        'pricePerServing': detailed_recipe.get('pricePerServing'),
        'diets': detailed_recipe.get('diets', []),
        'dishTypes': detailed_recipe.get('dishTypes', []),
        'cuisines': detailed_recipe.get('cuisines', []),
        'is_indian': is_indian,
        'api': 'spoonacular'
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
        'ingredients': [{'name': ing['name'], 'amount': ing['amount'], 'unit': ing['unit'], 'original': f"{ing['amount']} {ing['unit']} {ing['name']}"} 
                       for ing in indian_recipe['ingredients']],
        'ingredients_count': len(indian_recipe['ingredients']),
        'cooking_time': indian_recipe['cooking_time'],
        'servings': indian_recipe['servings'],
        'has_all_ingredients': False,
        'missing_ingredients': [],
        'tags': indian_recipe['tags'],
        'sourceUrl': '',
        'spoonacularSourceUrl': '',
        'healthScore': None,
        'pricePerServing': None,
        'diets': [],
        'dishTypes': [indian_recipe['category']],
        'cuisines': ['Indian'],
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
    
    
    user_ing = user_ing.translate(str.maketrans('', '', string.punctuation))
    recipe_ing = recipe_ing.translate(str.maketrans('', '', string.punctuation))
    
    
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
    
    return False


def check_ingredient_match(user_ingredient, recipe_ingredient):
    """
    Wrapper function for backward compatibility
    Uses the new smart matching
    """
    return _check_ingredient_match_smart(user_ingredient, recipe_ingredient)