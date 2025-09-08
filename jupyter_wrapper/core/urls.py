from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('project/create', views.create_project, name='create_project'),
    path('project/<int:project_id>', views.project_detail, name='project_detail'),
    path('project/<int:project_id>/notebook/create', views.create_notebook, name='create_notebook'),
    path('signup/', views.signup, name='signup'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('project/<int:project_id>/delete/', views.delete_project, name='delete_project'),
    path('notebook/<int:notebook_id>/delete/', views.delete_notebook, name='delete_notebook'),

]
