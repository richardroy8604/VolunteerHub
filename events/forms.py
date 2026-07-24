"""
Forms for event creation and editing with timeline validation rules.
"""

from django import forms
from datetime import date
from .models import Event


class EventForm(forms.ModelForm):
    max_volunteers = forms.IntegerField(required=False, initial=100, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Leave empty for default (100)'}))
    allocation_mode = forms.CharField(required=False, initial='manual', widget=forms.HiddenInput())

    class Meta:
        model = Event
        fields = [
            'name',
            'description',
            'venue',
            'start_date',
            'end_date',
            'registration_deadline',
            'max_volunteers',
            'allocation_mode',
            'banner',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Rajagiri Tech Fest 2026', 'required': True}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Provide a summary of volunteering activities...', 'required': True}),
            'venue': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Main Auditorium', 'required': True}),
            'max_volunteers': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Leave empty for default'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'required': True}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'required': True}),
            'registration_deadline': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'required': True}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        registration_deadline = cleaned_data.get('registration_deadline')
        from django.utils import timezone
        today = timezone.localtime(timezone.now()).date()

        # 1. Past date prevention for new events
        if not self.instance.pk:
            if start_date and start_date < today:
                self.add_error('start_date', 'Event start date cannot be set in the past.')
            if registration_deadline and registration_deadline < today:
                self.add_error('registration_deadline', 'Registration deadline cannot be set in the past.')

        # 2. End date >= Start date
        if start_date and end_date:
            if end_date < start_date:
                self.add_error('end_date', 'Event end date cannot be earlier than the start date.')

        # 3. Registration deadline at least 2 days BEFORE start date
        if registration_deadline and start_date:
            days_buffer = (start_date - registration_deadline).days
            if registration_deadline >= start_date:
                self.add_error('registration_deadline', 'Registration deadline must be before the event start date.')
            elif days_buffer < 2:
                self.add_error(
                    'registration_deadline',
                    f'Registration deadline must be at least 2 days before event start date (current gap: {days_buffer} day{"s" if days_buffer != 1 else ""}).'
                )

        # 4. Protection against shrinking event dates below logged attendance sheets
        if self.instance and self.instance.pk:
            from volunteers.models import AttendanceSheet
            sheets = AttendanceSheet.objects.filter(committee__event=self.instance)
            if sheets.exists():
                earliest_sheet = sheets.order_by('date').first()
                latest_sheet = sheets.order_by('-date').first()

                if start_date and earliest_sheet and start_date > earliest_sheet.date:
                    self.add_error(
                        'start_date',
                        f'Cannot set start date to {start_date.strftime("%b %d, %Y")} because attendance sheets have already been logged starting on {earliest_sheet.date.strftime("%b %d, %Y")}.'
                    )
                if end_date and latest_sheet and end_date < latest_sheet.date:
                    self.add_error(
                        'end_date',
                        f'Cannot set end date to {end_date.strftime("%b %d, %Y")} because attendance sheets have already been logged up to {latest_sheet.date.strftime("%b %d, %Y")}.'
                    )

        return cleaned_data

    def save(self, commit=True):
        event = super().save(commit=commit)
        if event.venue and event.venue.strip():
            from .models import Venue
            Venue.objects.get_or_create(name=event.venue.strip())
        return event
