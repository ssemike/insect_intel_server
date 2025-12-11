from django.urls import path
from . import views

urlpatterns = [
    path('', views.SimpleUploadView.as_view(), name='home for insect intel'),
    ]