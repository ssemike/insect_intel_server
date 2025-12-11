from django.urls import path
from . import views
from .views import landing_page_view

urlpatterns = [
    path('', landing_page_view, name='landing'),
    path('/upload', views.SimpleUploadView.as_view(), name='home for insect intel'),
    ]