from django import forms
from .models import TournamentSubscription


class TournamentSubscriptionForm(forms.ModelForm):
    class Meta:
        model = TournamentSubscription
        fields = []  # Add fields if you need additional info during subscription

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add payment method selection if needed