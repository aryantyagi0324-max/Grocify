import requests
import json
import random
from django.core.cache import cache
from django.conf import settings

def get_recipes_by_ingredients(ingredients, number=5):
    """
    Get recipes based on available ingredients using TheMealDB API
    ingredients: list of ingredient names
    number: number of recipes to return
    """
    
    if not ingredients:
        return {
            'error': 'No ingredients provided',
            'recipes': []
        }
    
    # Try multiple API strategies
    results = []
    
    # Strategy 1: Search by main ingredient
    for ingredient in ingredients[:3]:  # Try first 3 ingredients
        recipes = _search_by_ingredient(ingredient)
        if recipes:
            results.extend(recipes)
    
    # Strategy 2: Get random recipes (fallback)
    if len(results) < number:
        random_recipes = _get_random_recipes(number - len(results))
        results.extend(random_recipes)
    
    # Limit to requested number and remove duplicates
    unique_results = []
    seen_ids = set()
    
    for recipe in results:
        if recipe.get('id') and recipe['id'] not in seen_ids:
            seen_ids.add(recipe['id'])
            unique_results.append(recipe)
    
    # Format for template
    formatted_recipes = []
    for recipe in unique_results[:number]:
        formatted_recipe = _format_recipe(recipe)
        formatted_recipes.append(formatted_recipe)
    
    return {
        'success': True,
        'recipes': formatted_recipes,
        'total_recipes': len(formatted_recipes),
        'api_used': 'TheMealDB',
        'ingredients_searched': ingredients[:3]
    }

def _search_by_ingredient(ingredient):
    """Search recipes by ingredient using TheMealDB"""
    cache_key = f"mealdb_ingredient_{ingredient}"
    cached = cache.get(cache_key)
    
    if cached:
        return cached
    
    try:
        # TheMealDB API - filter by ingredient
        url = f"https://www.themealdb.com/api/json/v1/1/filter.php"
        params = {'i': ingredient.lower()}
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            meals = data.get('meals', [])
            
            # Get detailed info for each meal
            detailed_meals = []
            for meal in meals[:5]:  # Limit to 5
                meal_id = meal.get('idMeal')
                if meal_id:
                    details = _get_meal_details(meal_id)
                    if details:
                        detailed_meals.append(details)
            
            # Cache for 24 hours (API is free but let's be nice)
            cache.set(cache_key, detailed_meals, 86400)
            return detailed_meals
            
    except Exception as e:
        print(f"Error searching by ingredient {ingredient}: {e}")
    
    return []

def _get_meal_details(meal_id):
    """Get detailed meal information"""
    cache_key = f"mealdb_details_{meal_id}"
    cached = cache.get(cache_key)
    
    if cached:
        return cached
    
    try:
        url = f"https://www.themealdb.com/api/json/v1/1/lookup.php"
        params = {'i': meal_id}
        
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
                
                # Cache for 24 hours
                cache.set(cache_key, formatted_meal, 86400)
                return formatted_meal
                
    except Exception as e:
        print(f"Error getting meal details {meal_id}: {e}")
    
    return None

def _get_random_recipes(number=3):
    """Get random recipes as fallback"""
    cache_key = f"mealdb_random_{number}"
    cached = cache.get(cache_key)
    
    if cached:
        return cached
    
    try:
        random_meals = []
        
        # Get multiple random meals
        for _ in range(min(number * 2, 10)):  # Get extra to ensure we have enough
            url = "https://www.themealdb.com/api/json/v1/1/random.php"
            response = requests.get(url, timeout=10)
            
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
                        'instructions': meal.get('strInstructions', '')[:200] + '...' if meal.get('strInstructions') else '',
                    }
                    random_meals.append(formatted_meal)
        
        # Cache for 1 hour
        cache.set(cache_key, random_meals, 3600)
        return random_meals
        
    except Exception as e:
        print(f"Error getting random recipes: {e}")
    
    return []

def _format_recipe(meal):
    """Format meal data for template"""
    # Calculate approximate cooking time based on instructions length
    instructions = meal.get('instructions', '')
    word_count = len(instructions.split())
    cooking_time = max(15, min(120, word_count // 10))  # Rough estimate
    
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
        'short_instructions': instructions[:150] + '...' if len(instructions) > 150 else instructions,
        'image': meal.get('image', ''),
        'youtube': meal.get('youtube', ''),
        'source': meal.get('source', ''),
        'ingredients': ingredient_list,
        'ingredients_count': len(ingredient_list),
        'cooking_time': cooking_time,
        'servings': 4,  # Default assumption
        'has_all_ingredients': has_all_ingredients,
        'missing_ingredients': [],  # We don't have this info from TheMealDB
        'tags': meal.get('tags', [])
    }

def get_recipe_suggestions(user_items):
    """
    Get recipe suggestions based on user's inventory
    user_items: QuerySet of FoodItem objects
    """
    # Extract ingredient names
    ingredients = [item.name.lower() for item in user_items if item.name]
    
    # Common ingredient mappings (to improve API matching)
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
        # Try to find a mapping
        mapped = ingredient_mappings.get(ingredient, ingredient)
        # Remove plural 's' for better matching
        if mapped.endswith('s'):
            mapped = mapped[:-1]
        mapped_ingredients.append(mapped)
    
    # Remove duplicates
    unique_ingredients = list(set(mapped_ingredients))
    
    # Limit to 5 ingredients to avoid too many API calls
    search_ingredients = unique_ingredients[:5]
    
    if not search_ingredients:
        return {
            'error': 'No ingredients in inventory',
            'recipes': []
        }
    
    return get_recipes_by_ingredients(search_ingredients, number=6)