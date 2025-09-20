from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse, HttpResponse
from .models import Project, Notebook , BusinessGroup , Notebook , NotebookRun, ScheduleStep, Schedule
import os
from nbformat import v4,read,write
from nbclient import NotebookClient
from django.shortcuts import get_object_or_404, redirect
from django.conf import settings
import shutil
from .forms import ProjectForm, NotebookForm
from django.views.decorators.csrf import csrf_exempt
import json 
from django.utils import timezone
from datetime import datetime
from django.utils.dateparse import parse_datetime
from django.template.loader import render_to_string
from django.contrib import messages


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
    group=None
    if hasattr(request.user,"group"):
        group = request.user.group
    
    projects = Project.objects.filter(group=group) #queries the db for all projects owned by the current user
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
    group=None
    if hasattr(request.user,"group"):
        group = request.user.group
    project = get_object_or_404(Project, id=project_id, group=group)
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
    project = get_object_or_404(Project, id=project_id, group=request.user.group)

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


@csrf_exempt
@login_required
def toggle_schedule(request):
    """
    Handle the ON/OFF slider for scheduling.
    """
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        notebook_id = data.get("notebook_id")
        is_scheduled = data.get("is_scheduled")

        notebook = get_object_or_404(Notebook, id=notebook_id, project__user=request.user)

        notebook.is_scheduled = is_scheduled
        notebook.save()

        # TODO: Enable/disable Airflow DAG via REST API

        return JsonResponse({"status": "success", "scheduled": notebook.is_scheduled})

    return JsonResponse({"error": "Invalid request"}, status=400)


AIRFLOW_DAGS_FOLDER = "/mnt/c/Users/revin/Documents/Projects/airflow/dags"
DAG_TEMPLATE_PATH = "/mnt/c/Users/revin/Documents/Projects/airflow/notebook_dag_template.py"
DAG_TEMPLATE_PATH_SEQ = "/mnt/c/Users/revin/Documents/Projects/airflow/notebook_sequence_dag_template.py"

def convert_to_cron(seconds, minutes, hours, start_time):
    """
    Convert user input into a cron expression.
    Airflow supports cron format like: '0 30 * * *' (min, hour, dom, month, dow)
    We'll ignore seconds because cron only supports minutes and above.
    """
    start_dt = parse_datetime(start_time)
    if not start_dt:
        start_dt = None

    cron_minute = (start_dt.minute if start_dt else 0) + int(minutes)
    cron_hour = (start_dt.hour if start_dt else 0) + int(hours)
    # For simplicity, we will ignore seconds in cron
    cron_expression = f"{cron_minute} {cron_hour} * * *"
    return cron_expression

def create_dag_file(notebook):
    # Read template
    with open(DAG_TEMPLATE_PATH, "r") as f:
        template = f.read()

    # Convert to cron
    cron_expression = convert_to_cron(
        notebook.schedule_seconds,
        notebook.schedule_minutes,
        notebook.schedule_hours,
        notebook.start_time.isoformat() if notebook.start_time else ""
    )

    # Replace placeholders
    content = template.replace("{{NOTEBOOK_ID}}", str(notebook.id))
    content = content.replace("{{CRON_EXPRESSION}}", cron_expression)
    content = content.replace("{{NOTEBOOK_PATH}}", notebook.file_path)

    # Save to DAGs folder
    dag_file_path = os.path.join(AIRFLOW_DAGS_FOLDER, f"notebook_{notebook.id}.py")
    with open(dag_file_path, "w") as f:
        f.write(content)

    return dag_file_path

def schedule_notebook(request):
    if request.method == "POST":
        notebook_id = request.POST.get("notebook_id")
        notebook = get_object_or_404(Notebook, id=notebook_id)

        # Get schedule from form
        seconds = int(request.POST.get("seconds", 0))
        minutes = int(request.POST.get("minutes", 0))
        hours = int(request.POST.get("hours", 0))
        start_time = request.POST.get("start_time")  # 'YYYY-MM-DDTHH:MM'

        # Convert to cron (Airflow ignores seconds)
        cron_expr = f"{minutes} {hours} * * *"

        # Read template
        with open(DAG_TEMPLATE_PATH, "r") as f:
            template = f.read()

        # Replace placeholders
        dag_content = template.replace("{{ NOTEBOOK_ID }}", str(notebook.id)) \
                              .replace("{{ NOTEBOOK_PATH }}", notebook.file_path) \
                              .replace("{{ CRON_EXPRESSION }}", cron_expr) \
                              .replace("{{ START_TIME }}", start_time if start_time else "None")

        # Write DAG file
        dag_filename = f"notebook_{notebook.id}.py"
        dag_path = os.path.join(AIRFLOW_DAGS_FOLDER, dag_filename)
        with open(dag_path, "w") as f:
            f.write(dag_content)

        # Update notebook record
        notebook.is_scheduled = True
        notebook.schedule_hours = hours
        notebook.schedule_minutes = minutes
        notebook.schedule_seconds = seconds
        notebook.start_time = start_time if start_time else None
        notebook.airflow_dag_id = f"notebook_{notebook.id}"
        notebook.save()

        return redirect("project_detail", project_id=notebook.project.id)
    
@csrf_exempt
def notebook_run_create(request):
    data = json.loads(request.body)
    notebook = Notebook.objects.get(id=data['notebook_id'])
    run = NotebookRun.objects.create(notebook=notebook)
    return JsonResponse({"run_id": run.id})

@csrf_exempt
def notebook_run_update(request):
    data = json.loads(request.body)
    run = NotebookRun.objects.get(id=data['run_id'])
    run.status = data['status']
    run.log = data.get('log', '')
    run.finished_at = datetime.now()
    run.save()
    return JsonResponse({"success": True})



def create_schedule(request, project_id):
    if request.method == "POST":
        project = get_object_or_404(Project, id=project_id)

        # Get form data
        schedule_name = request.POST.get("schedule_name", "").strip()  # Ensure name is not empty or whitespace
        notebook_ids = request.POST.getlist("notebooks")  # ordered
        seconds = int(request.POST.get("seconds") or 0)
        minutes = int(request.POST.get("minutes") or 0)
        hours = int(request.POST.get("hours") or 0)
        start_time_str = request.POST.get("start_time")

        # Validate schedule name
        if not schedule_name:
            return HttpResponse("Schedule name is required.", status=400)

        if not notebook_ids:
            return HttpResponse("Please select at least one notebook.", status=400)

        # Convert start_time string to datetime
        start_time = parse_datetime(start_time_str)
        if not start_time:
            return HttpResponse("Invalid start time format", status=400)

        # Convert to cron expression
        cron = f"{start_time.minute} {start_time.hour} */{hours or 1} * *"

        # Create Schedule entry
        schedule = Schedule.objects.create(
            project=project,
            name=schedule_name,
            start_time=start_time,
            cron_expression=cron
        )

        # Add steps in order
        for idx, notebook_id in enumerate(notebook_ids):
            notebook = get_object_or_404(Notebook, id=notebook_id)
            ScheduleStep.objects.create(
                schedule=schedule,
                notebook=notebook,
                order=idx + 1
            )

        # Create DAG file
        with open(DAG_TEMPLATE_PATH_SEQ, "r") as f:
            template_content = f.read()

        # Replace placeholders
        dag_content = template_content.replace("{{DAG_ID}}", f"schedule_{schedule.id}") \
                                      .replace("{{CRON_EXPRESSION}}", cron) \
                                      .replace("{{NOTEBOOK_IDS}}", str(notebook_ids)) \
                                      .replace("{{SCHEDULE_NAME}}", schedule_name)

        # Save DAG file
        dag_filename = f"schedule_{schedule.id}.py"
        dag_path = os.path.join(AIRFLOW_DAGS_FOLDER, dag_filename)
        with open(dag_path, "w") as f:
            f.write(dag_content)

        return redirect("project_detail", project_id=project.id)
    else:
        return HttpResponse("Invalid request", status=405)
