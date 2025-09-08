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
from .forms import ProjectForm, NotebookForm


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
    form = ProjectForm(user=request.user) #creates an instance of the ProjectForm, passing the current user to it
    return render(request, 'dashboard.html', {'projects': projects ,'form':form}) #renders the dashboard.html template with the user's projects

@login_required
def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST, user=request.user)
        if form.is_valid():
            project = form.save(commit=False)
            project.user = request.user
            project.save()
            return redirect('dashboard')
        else:
            projects=Project.objects.filter(user=request.user)
            return render(request,'dashboard.html',{'form':form,'projects':projects})
    else:
        return redirect('dashboard')
        


@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)
    notebooks = Notebook.objects.filter(project=project)
    form = NotebookForm(project=project)

    for nb in notebooks:
        nb.jupyter_url=f"http://localhost:8888/lab/tree/{project.id}/{nb.name}.ipynb"

    return render(request, 'project_detail.html', {'project': project, 'notebooks': notebooks, 'form': form})


@login_required
def create_notebook(request,project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)

    if request.method == 'POST':
        form = NotebookForm(request.POST, project=project , user = request.user)
        if form.is_valid():
            notebook = form.save(commit=False)
            notebook.project = project
            notebook.user = request.user
            file_path = os.path.join(BASE_NOTEBOOK_DIR, str(project.id), f"{notebook.name}.ipynb")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            nb = v4.new_notebook()
            with open(file_path, 'w') as f:
                write(nb, f)
            notebook.file_path = file_path
            notebook.save()
            return redirect('project_detail', project_id=project.id)
        else:
            notebooks = Notebook.objects.filter(project=project)
            return render(request, 'project_detail.html', {'project': project, 'notebooks': notebooks, 'form': form})
    else:
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

