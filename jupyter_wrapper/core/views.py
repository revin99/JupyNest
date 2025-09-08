from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from .models import Project, Notebook
import os
from nbformat import v4,read,write
from nbclient import NotebookClient
from django.shortcuts import get_object_or_404, redirect
from django.conf import settings
import shutil


BASE_NOTEBOOK_DIR = os.path.join(os.getcwd(), "user_notebooks")
os.makedirs(BASE_NOTEBOOK_DIR, exist_ok=True)
# Create your views here.

def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})

@login_required
def dashboard(request):
    projects = Project.objects.filter(user=request.user) #queries the db for all projects owned by the current user
    return render(request, 'dashboard.html', {'projects': projects}) #renders the dashboard.html template with the user's projects

@login_required
def create_project(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            # Create new project in DB
            project = Project.objects.create(user=request.user, name=name)

            # Create project folder for notebooks
            project_dir = os.path.join(BASE_NOTEBOOK_DIR, str(project.id))
            os.makedirs(project_dir, exist_ok=True)  # ✅ ensures folder exists

        # Redirect back to dashboard; modal disappears
        return redirect('dashboard')

@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)
    notebooks = Notebook.objects.filter(project=project)

    for nb in notebooks:
        nb.jupyter_url=f"http://localhost:8888/lab/tree/{project.id}/{nb.name}.ipynb"

    return render(request, 'project_detail.html', {'project': project, 'notebooks': notebooks})


@login_required
def create_notebook(request,project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)

    if request.method == 'POST':
        name = request.POST.get('name')
        file_path = os.path.join(BASE_NOTEBOOK_DIR, str(project.id), f"{name}.ipynb")
        nb = v4.new_notebook()
        with open(file_path, 'w') as f:
            write(nb,f)
        notebook = Notebook.objects.create(project=project, name=name, file_path=file_path)
    return redirect('project_detail', project_id=project.id)

@login_required
def delete_project(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)

    # Delete project folder (all notebooks inside)
    project_slug = project.name.replace(" ", "_")  # or use slugify if you prefer
    project_dir = os.path.join(settings.BASE_NOTEBOOK_DIR, project_slug)
    if os.path.exists(project_dir):
        shutil.rmtree(project_dir)

    # Delete project in DB (will cascade to notebooks)
    project.delete()
    return redirect('dashboard')

@login_required
def delete_notebook(request, notebook_id):
    notebook = get_object_or_404(Notebook, id=notebook_id, project__user=request.user)

    # Delete notebook file
    if os.path.exists(notebook.file_path):
        os.remove(notebook.file_path)

    # Delete notebook in DB
    notebook.delete()
    return redirect('project_detail', project_id=notebook.project.id)
