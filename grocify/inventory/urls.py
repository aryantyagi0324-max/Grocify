from django.urls import path
from grocify.grocify import views as pages

urlpatterns = [
    path('', pages.landing_page, name='landing'),
]
