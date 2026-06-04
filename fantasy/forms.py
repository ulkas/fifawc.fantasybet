from django import forms

from .models import Prediction


class GateForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))


class JoinForm(forms.Form):
    mode = forms.ChoiceField(choices=[("register", "Register"), ("login", "Login")], widget=forms.HiddenInput)
    nick = forms.CharField(max_length=60)
    pin = forms.CharField(max_length=64, widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))


class PredictionForm(forms.Form):
    choice = forms.ChoiceField(choices=Prediction.Choice.choices, widget=forms.RadioSelect)
