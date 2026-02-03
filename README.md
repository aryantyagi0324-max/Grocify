Grocify - Smart Kitchen Inventory Management System

🚀 Overview
-> Grocify is a full-featured Django web application that helps users manage their kitchen inventory, track food expiry dates, and get smart recipe suggestions based on available ingredients. The system is designed to reduce food waste, save money, and make meal planning easier.

✨ Features
🛠️ Core Features

->User Authentication & Authorization: Secure signup, login, and logout with session management
->Food Inventory Management: Full CRUD operations for food items with categories
->Smart Expiry Tracking: Automated expiry date calculation with color-coded alerts
->Quick Add Mode: Add multiple items at once with batch saving
->Search & Filter: Filter items by category and search by name
->Dark/Light Theme: User-friendly theme toggle for better UX

🧠 Smart Features

->Intelligent Recipe Suggestions: Get recipe ideas based on your current inventory
->Spoonacular API Integration: Access thousands of recipes with detailed instructions
->Fallback Indian Recipes: Default recipes when API is unavailable
->Ingredient Matching Algorithm: Smart matching between inventory and recipe ingredients
->Expiry Status Calculation: Automatic calculation of days until expiry

📱 UI/UX Features

->Responsive Design: Works on desktop, tablet, and mobile
->Modern Interface: Clean, intuitive interface with Font Awesome icons
->Real-time Validation: Instant form validation with helpful error messages
->Progress Indicators: Loading spinners and success notifications
->Accessibility: Keyboard navigation and screen reader support

🏗️ Technology Stack
Backend

->Framework: Django 4.x
->Database: SQLite3 (can be easily migrated to PostgreSQL)
->Authentication: Django's built-in authentication system
->API Integration: Spoonacular Food API
->Caching: Django's cache framework for API responses

Frontend

->HTML5: Semantic markup
->CSS3: Custom CSS with CSS variables for theming
->JavaScript: Vanilla JavaScript for interactivity
->Icons: Font Awesome 6.4.0
->Fonts: Google Fonts (Poppins, Inter)

APIs

->Primary: Spoonacular Food API for recipe data
->Backup: Built-in Indian recipe database as fallback

🚀 Installation & Setup
Prerequisites

->Python 3.8 or higher
->pip (Python package manager)
->Git

Step 1: Clone the Repository

git clone <your-repository-url>
cd grocify

Step 2: Create Virtual Environment

# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate

Step 3: Install Dependencies

pip install django requests

Step 4: Configure Environment Variables

SECRET_KEY=your-django-secret-key-here
SPOONACULAR_API_KEY=your-spoonacular-api-key-here
DEBUG=True

Step 5: Apply Migrations

python manage.py makemigrations
python manage.py migrate

Step 6: Create Superuser (Optional)

python manage.py createsuperuser

Step 7: Run Development Server

python manage.py runserver
Visit http://127.0.0.1:8000/ in your browser.

🔑 Key Features Explained

1. Quick Add Mode 
->Purpose: Add multiple items without leaving the page
How it works:
->Enable Quick Add mode
->Fill form and click "Add to Quick List"
->Repeat for multiple items
->Click "Save All Items" to save everything at once
->Benefits: Faster data entry, better user experience

2. Smart Expiry Tracking
 
->Status Levels:
✅ Good (7+ days remaining)
⏳ Expiring Soon (3-7 days)
🔥 Expires Today (0 days)
⛔ Expired (negative days)
->Color Coding: Visual indicators for quick scanning
->Automated Calculation: Updates automatically based on current date

3. Recipe Suggestions

->Algorithm: Matches your inventory with recipe ingredients
->Percentage Match: Shows how many ingredients you have
->Feasibility Score: High/Medium/Low based on match percentage
->Fallback System: Uses Indian recipes if API fails

4. Theme Toggle
 
->Light/Dark Mode: User preference saved in localStorage
->CSS Variables: Easy theme customization
->Smooth Transitions: Animated theme switching
