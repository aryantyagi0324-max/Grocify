import requests
import json
import random
from django.core.cache import cache
from django.conf import settings
import concurrent.futures

def get_recipes_by_ingredients(ingredients, number=5):
    """
    Get recipes based on available ingredients
    WITH ENHANCED CACHING for performance
    """
    if not ingredients:
        return {
            'error': 'No ingredients provided',
            'recipes': []
        }
    
    # Create cache key based on ingredients
    ingredients_key = '_'.join(sorted([ing.lower().replace(' ', '_') for ing in ingredients[:3]]))
    cache_key = f"recipes_{ingredients_key}_{number}"
    
    # Try to get from cache first
    cached = cache.get(cache_key)
    if cached:
        print(f"✅ Using cached recipes for: {ingredients[:3]}")
        cached['cached'] = True
        return cached
    
    print(f"🔄 Fetching fresh recipes for: {ingredients[:3]}")
    
    # Try multiple strategies
    results = []
    
    # Strategy 1: Search by main ingredient (with parallel processing)
    def fetch_ingredient_recipes(ingredient):
        return _search_by_ingredient(ingredient)
    
    # Fetch first 3 ingredients in parallel
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(fetch_ingredient_recipes, ingredient) 
                      for ingredient in ingredients[:3]]
            
            for future in concurrent.futures.as_completed(futures, timeout=8):
                try:
                    recipes = future.result(timeout=5)
                    if recipes:
                        results.extend(recipes[:3])  # Limit to 3 per ingredient
                except Exception as e:
                    print(f"Error fetching ingredient recipes: {e}")
    except Exception as e:
        print(f"Parallel processing error: {e}")
        # Fallback to sequential
        for ingredient in ingredients[:3]:
            try:
                recipes = _search_by_ingredient(ingredient)
                if recipes:
                    results.extend(recipes[:2])
            except:
                pass
    
    # Strategy 2: Get random recipes (fallback)
    if len(results) < number:
        try:
            random_recipes = _get_random_recipes(number - len(results))
            results.extend(random_recipes)
        except:
            pass
    
    # Limit to requested number and remove duplicates
    unique_results = []
    seen_ids = set()
    
    for recipe in results:
        if recipe and recipe.get('id') and recipe['id'] not in seen_ids:
            seen_ids.add(recipe['id'])
            unique_results.append(recipe)
    
    # Format for template
    formatted_recipes = []
    for recipe in unique_results[:number]:
        formatted_recipe = _format_recipe(recipe)
        formatted_recipes.append(formatted_recipe)
    
    response = {
        'success': True,
        'recipes': formatted_recipes,
        'total_recipes': len(formatted_recipes),
        'ingredients_searched': ingredients[:3],
        'cached': False,
        'load_time': 'fresh'
    }
    
    # Cache for 4 hours
    cache.set(cache_key, response, 14400)
    
    return response

def _search_by_ingredient(ingredient):
    """Search recipes by ingredient - OPTIMIZED"""
    cache_key = f"ingredient_{ingredient.lower().replace(' ', '_')}"
    cached = cache.get(cache_key)
    
    if cached:
        return cached
    
    try:
        # Recipe search endpoint
        url = "https://www.themealdb.com/api/json/v1/1/filter.php"
        params = {'i': ingredient.lower()}
        
        response = requests.get(url, params=params, timeout=6)
        
        if response.status_code == 200:
            data = response.json()
            meals = data.get('meals', [])
            
            if not meals:
                cache.set(cache_key, [], 3600)
                return []
            
            # Get basic details for first 5 meals
            basic_meals = []
            for meal in meals[:5]:
                meal_id = meal.get('idMeal')
                if meal_id:
                    basic_info = _get_basic_meal_info(meal_id)
                    if basic_info:
                        basic_meals.append(basic_info)
            
            cache.set(cache_key, basic_meals, 28800)
            return basic_meals
            
    except Exception as e:
        print(f"Error searching by ingredient {ingredient}: {e}")
        cache.set(cache_key, [], 900)
    
    return []

def _get_basic_meal_info(meal_id):
    """Get basic meal information (optimized for speed)"""
    cache_key = f"basic_{meal_id}"
    cached = cache.get(cache_key)
    
    if cached:
        return cached
    
    try:
        url = f"https://www.themealdb.com/api/json/v1/1/lookup.php"
        params = {'i': meal_id}
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            meals = data.get('meals', [])
            
            if meals:
                meal = meals[0]
                
                # Get only 5 main ingredients for basic view
                ingredients = []
                for i in range(1, 6):
                    ingredient = meal.get(f'strIngredient{i}', '').strip()
                    measure = meal.get(f'strMeasure{i}', '').strip()
                    
                    if ingredient:
                        ingredients.append({
                            'name': ingredient,
                            'measure': measure
                        })
                
                # Basic meal data
                basic_meal = {
                    'id': meal.get('idMeal'),
                    'title': meal.get('strMeal', 'Unknown Recipe'),
                    'category': meal.get('strCategory', ''),
                    'image': meal.get('strMealThumb', ''),
                    'ingredients': ingredients,
                    'instructions': (meal.get('strInstructions', '')[:100] + '...') if meal.get('strInstructions') else '',
                }
                
                cache.set(cache_key, basic_meal, 43200)
                return basic_meal
                
    except Exception as e:
        print(f"Error getting basic meal info {meal_id}: {e}")
    
    return None

def _get_meal_details(meal_id):
    """Get detailed meal information (only for recipe detail page)"""
    cache_key = f"details_{meal_id}"
    cached = cache.get(cache_key)
    
    if cached:
        return cached
    
    try:
        url = f"https://www.themealdb.com/api/json/v1/1/lookup.php"
        params = {'i': meal_id}
        
        response = requests.get(url, params=params, timeout=8)
        
        if response.status_code == 200:
            data = response.json()
            meals = data.get('meals', [])
            
            if meals:
                meal = meals[0]
                
                # Extract ingredients and measures
                ingredients = []
                for i in range(1, 21):
                    ingredient = meal.get(f'strIngredient{i}', '').strip()
                    measure = meal.get(f'strMeasure{i}', '').strip()
                    
                    if ingredient:
                        ingredients.append({
                            'name': ingredient,
                            'measure': measure
                        })
                
                # Format the meal data
                formatted_meal = {
                    'id': meal.get('idMeal'),
                    'title': meal.get('strMeal', 'Unknown Recipe'),
                    'category': meal.get('strCategory', ''),
                    'area': meal.get('strArea', ''),
                    'instructions': meal.get('strInstructions', ''),
                    'image': meal.get('strMealThumb', ''),
                    'youtube': meal.get('strYoutube', ''),
                    'source': meal.get('strSource', ''),
                    'ingredients': ingredients,
                    'tags': meal.get('strTags', '').split(',') if meal.get('strTags') else [],
                }
                
                cache.set(cache_key, formatted_meal, 86400)
                return formatted_meal
                
    except Exception as e:
        print(f"Error getting meal details {meal_id}: {e}")
    
    return None

def _get_random_recipes(number=3):
    """Get random recipes as fallback - OPTIMIZED"""
    cache_key = f"random_{number}"
    cached = cache.get(cache_key)
    
    if cached:
        return cached
    
    try:
        random_meals = []
        
        for _ in range(min(number, 3)):
            url = "https://www.themealdb.com/api/json/v1/1/random.php"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                meals = data.get('meals', [])
                
                if meals:
                    meal = meals[0]
                    formatted_meal = {
                        'id': meal.get('idMeal'),
                        'title': meal.get('strMeal', 'Unknown Recipe'),
                        'category': meal.get('strCategory', ''),
                        'image': meal.get('strMealThumb', ''),
                        'instructions': (meal.get('strInstructions', '')[:150] + '...') if meal.get('strInstructions') else '',
                    }
                    random_meals.append(formatted_meal)
        
        cache.set(cache_key, random_meals, 7200)
        return random_meals
        
    except Exception as e:
        print(f"Error getting random recipes: {e}")
    
    return []

def _format_recipe(meal):
    """Format meal data for template"""
    # Calculate approximate cooking time
    instructions = meal.get('instructions', '')
    word_count = len(instructions.split())
    cooking_time = max(15, min(120, word_count // 10))
    
    # Create ingredient list for display
    ingredient_list = []
    for ing in meal.get('ingredients', []):
        if ing['name']:
            display = f"{ing['measure']} {ing['name']}".strip()
            ingredient_list.append(display)
    
    # Check if we have all ingredients (simplified logic)
    has_all_ingredients = len(ingredient_list) > 0
    
    return {
        'id': meal.get('id', ''),
        'title': meal.get('title', 'Unknown Recipe'),
        'category': meal.get('category', 'General'),
        'area': meal.get('area', ''),
        'instructions': instructions,
        'short_instructions': instructions[:120] + '...' if len(instructions) > 120 else instructions,
        'image': meal.get('image', ''),
        'youtube': meal.get('youtube', ''),
        'source': meal.get('source', ''),
        'ingredients': ingredient_list,
        'ingredients_count': len(ingredient_list),
        'cooking_time': cooking_time,
        'servings': 4,
        'has_all_ingredients': has_all_ingredients,
        'missing_ingredients': [],
        'tags': meal.get('tags', [])
    }

def get_recipe_suggestions(user_items):
    """
    Get recipe suggestions based on user's inventory - OPTIMIZED
    """
    # Extract ingredient names
    ingredients = [item.name.lower() for item in user_items if item.name]
    
    # Common ingredient mappings
    ingredient_mappings = {
        'milk': 'milk',
        'bread': 'bread',
        'egg': 'egg',
        'cheese': 'cheese',
        'tomato': 'tomato',
        'chicken': 'chicken',
        'rice': 'rice',
        'pasta': 'pasta',
        'potato': 'potato',
        'onion': 'onion',
        'garlic': 'garlic',
        'butter': 'butter',
        'flour': 'flour',
        'sugar': 'sugar',
        'salt': 'salt',
        'pepper': 'pepper',
        'oil': 'oil',
        'beef': 'beef',
        'pork': 'pork',
        'fish': 'fish',
    }
    
    # Map ingredients to common names
    mapped_ingredients = []
    for ingredient in ingredients:
        mapped = ingredient_mappings.get(ingredient, ingredient)
        if mapped.endswith('s') and len(mapped) > 3:
            mapped = mapped[:-1]
        mapped_ingredients.append(mapped)
    
    # Remove duplicates
    unique_ingredients = list(set(mapped_ingredients))
    
    # Limit to 4 ingredients
    search_ingredients = unique_ingredients[:4]
    
    if not search_ingredients:
        return {
            'error': 'No ingredients in inventory',
            'recipes': [],
            'cached': True
        }
    
    recipe_data = get_recipes_by_ingredients(search_ingredients, number=6)
    return recipe_data