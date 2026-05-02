
from .models import StatSubmission
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Room
from django import forms



class CreateRoomForm(forms.ModelForm):
    game_password = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Optional password for private rooms',
            'maxlength': '10'
        }),
        help_text="Leave empty for public room"
    )

    class Meta:
        model = Room
        fields = ['title', 'game', 'description', 'max_players', 'game_password']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Describe your room, rules, or requirements...'
            }),
            'game': forms.Select(attrs={'class': 'game-select'})
        }

    def clean_game_password(self):
        password = self.cleaned_data.get('game_password', '').strip()
        if password and len(password) < 4:
            raise forms.ValidationError("Password must be at least 4 characters")
        return password

class StatSubmissionForm(forms.ModelForm):
    class Meta:
        model = StatSubmission
        fields = ['kills', 'deaths', 'wins', 'matches_played', 'screenshot', 'description']
        widgets = {
            'kills': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': 'Number of kills',
                'class': 'form-input'
            }),
            'deaths': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': 'Number of deaths',
                'class': 'form-input'
            }),
            'wins': forms.NumberInput(attrs={
                'min': 0,
                'placeholder': 'Number of wins',
                'class': 'form-input'
            }),
            'matches_played': forms.NumberInput(attrs={
                'min': 1,
                'placeholder': 'Matches played',
                'class': 'form-input'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Optional: Add any additional details about your gameplay...',
                'class': 'form-input'
            }),
            'screenshot': forms.ClearableFileInput(attrs={
                'accept': 'image/*',
                'class': 'form-input'
            })
        }

    def _init_(self, *args, **kwargs):
        super()._init_(*args, **kwargs)
        # Make fields required
        self.fields['kills'].required = True
        self.fields['deaths'].required = True
        self.fields['wins'].required = True
        self.fields['matches_played'].required = True
        self.fields['screenshot'].required = True





class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-input',
        'placeholder': 'your@email.com'
    }))

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user





class FPSStatSubmissionForm(forms.ModelForm):
    class Meta:
        model = StatSubmission
        fields = ['kills', 'deaths', 'wins', 'matches_played', 'screenshot', 'description']


class RacingStatSubmissionForm(forms.ModelForm):
    race_time = forms.CharField(required=True)
    race_position = forms.IntegerField(min_value=1, required=True)
    best_lap = forms.CharField(required=False)

    class Meta:
        model = StatSubmission
        fields = ['screenshot', 'description']


class FootballStatSubmissionForm(forms.ModelForm):
    goals = forms.IntegerField(min_value=0, required=True)
    assists = forms.IntegerField(min_value=0, required=True)
    clean_sheet = forms.BooleanField(required=False)

    class Meta:
        model = StatSubmission
        fields = ['matches_played', 'screenshot', 'description']


class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your name'
        })
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'your@email.com'
        })
    )

    subject = forms.ChoiceField(
        choices=[
            ('', 'Select a topic'),
            ('support', 'Technical Support'),
            ('account', 'Account Issues'),
            ('feedback', 'Feedback & Suggestions'),
            ('partnership', 'Partnership Inquiry'),
            ('other', 'Other'),
        ],
        widget=forms.Select(attrs={'class': 'form-input'})
    )

    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'placeholder': 'How can we help you?',
            'rows': 5
        })
    )