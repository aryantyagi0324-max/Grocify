"""
Default Indian recipes to suggest when API doesn't return good results
"""

INDIAN_RECIPES = [
    {
        'id': 'indian_1',
        'title': 'Vegetable Pulao',
        'category': 'Main Course',
        'image': 'https://via.placeholder.com/400x300/FF9933/FFFFFF?text=Vegetable+Pulao',
        'instructions': '1. Wash and soak rice for 30 minutes. 2. Heat oil/ghee in a pressure cooker. 3. Add whole spices (cumin, bay leaf, cloves). 4. Add chopped vegetables and sauté. 5. Add rice, water, and salt. 6. Pressure cook for 2 whistles.',
        'short_instructions': 'Aromatic rice dish with mixed vegetables and Indian spices.',
        'ingredients': [
            {'name': 'Basmati Rice', 'amount': 1, 'unit': 'cup'},
            {'name': 'Mixed Vegetables', 'amount': 2, 'unit': 'cups'},
            {'name': 'Onion', 'amount': 1, 'unit': 'large'},
            {'name': 'Ginger Garlic Paste', 'amount': 1, 'unit': 'tsp'},
            {'name': 'Garam Masala', 'amount': 1, 'unit': 'tsp'},
            {'name': 'Cumin Seeds', 'amount': 1, 'unit': 'tsp'},
            {'name': 'Oil/Ghee', 'amount': 2, 'unit': 'tbsp'},
            {'name': 'Salt', 'amount': 1, 'unit': 'tsp'},
        ],
        'cooking_time': 30,
        'servings': 4,
        'tags': ['Indian', 'Vegetarian', 'Rice', 'Main Course'],
        'is_indian': True,
    },
    {
        'id': 'indian_2',
        'title': 'Chana Masala',
        'category': 'Main Course',
        'image': 'https://via.placeholder.com/400x300/FF9933/FFFFFF?text=Chana+Masala',
        'instructions': '1. Soak chickpeas overnight. 2. Pressure cook until soft. 3. Heat oil in a pan. 4. Add cumin, onions, ginger-garlic paste. 5. Add tomatoes and spices. 6. Add cooked chickpeas and simmer.',
        'short_instructions': 'Spicy chickpea curry with Indian spices.',
        'ingredients': [
            {'name': 'Chickpeas', 'amount': 1, 'unit': 'cup'},
            {'name': 'Onion', 'amount': 2, 'unit': 'medium'},
            {'name': 'Tomatoes', 'amount': 3, 'unit': 'medium'},
            {'name': 'Ginger Garlic Paste', 'amount': 1, 'unit': 'tbsp'},
            {'name': 'Chana Masala Powder', 'amount': 2, 'unit': 'tbsp'},
            {'name': 'Turmeric Powder', 'amount': 0.5, 'unit': 'tsp'},
            {'name': 'Coriander Powder', 'amount': 1, 'unit': 'tsp'},
            {'name': 'Oil', 'amount': 3, 'unit': 'tbsp'},
        ],
        'cooking_time': 45,
        'servings': 4,
        'tags': ['Indian', 'Vegetarian', 'Curry', 'Chickpeas'],
        'is_indian': True,
    },
    # Add more Indian recipes as needed
]