# forms.py
from django import forms
from .models import Project , Notebook

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data['name']
        if Project.objects.filter(user=self.user, name=name).exists():
            raise forms.ValidationError("You already have a project with this name.")
        return name

class NotebookForm(forms.ModelForm):
    class Meta:
        model = Notebook
        fields = ['name']

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data['name']
        if self.project and Notebook.objects.filter(project=self.project, name=name).exists():
            raise forms.ValidationError("A notebook with this name already exists in this project.")
        return name

    