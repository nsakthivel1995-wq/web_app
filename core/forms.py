from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.forms import AuthenticationForm
from .models import (
    User,
    OrderDigitizing, OrderPatches, OrderVector,
    QuoteDigitizing, QuotePatches, QuoteVector,
    # Legacy (kept for admin display)
    Order, Quote,
    BillingInvoice, BillingInvoiceItem,
)


class RegisterForm(forms.ModelForm):
    first_name       = forms.CharField(max_length=150, min_length=2)
    last_name        = forms.CharField(max_length=150, min_length=1)
    email            = forms.EmailField()
    phone            = forms.CharField(max_length=15)
    password         = forms.CharField(widget=forms.PasswordInput, min_length=5)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    terms            = forms.BooleanField()

    class Meta:
        model  = User
        fields = ['first_name', 'last_name', 'email', 'phone']

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data['phone'].replace(' ', '')
        if not phone.isdigit() or len(phone) != 10:
            raise forms.ValidationError("Phone must be exactly 10 digits.")
        return phone

    def clean(self):
        cleaned = super().clean()
        pw  = cleaned.get('password', '')
        cpw = cleaned.get('confirm_password', '')
        if pw and cpw and pw != cpw:
            raise forms.ValidationError("Passwords do not match.")
        import re
        if pw and len(pw) < 8:
            raise forms.ValidationError("Password must be at least 8 characters.")
        if pw and not re.search(r'\d', pw):
            raise forms.ValidationError("Password must contain at least one number.")
        if pw and not re.search(r'[!@#$%^&*(),.?":{}|<>_\-]', pw):
            raise forms.ValidationError("Password must contain at least one special character.")
        return cleaned

    def save(self, commit=True):
        user          = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email    = self.cleaned_data['email']
        user.phone    = self.cleaned_data['phone']
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    username = forms.EmailField(label='Email', widget=forms.EmailInput)
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        return self.cleaned_data.get('username', '').lower().strip()


class _OrderQuoteValidationMixin:
    """Shared server-side validation for all 6 order/quote ModelForms."""

    def clean_design_name(self):
        name = self.cleaned_data.get('design_name', '').strip()
        if not name:
            raise forms.ValidationError("Design Name is required.")
        return name

    def clean_width_mm(self):
        v = self.cleaned_data.get('width_mm')
        if v is not None and v <= 0:
            raise forms.ValidationError("Width must be a positive number.")
        return v

    def clean_height_mm(self):
        v = self.cleaned_data.get('height_mm')
        if v is not None and v <= 0:
            raise forms.ValidationError("Height must be a positive number.")
        return v

    def clean_colors(self):
        v = self.cleaned_data.get('colors')
        if v is not None and v < 0:
            raise forms.ValidationError("Number of Colors cannot be negative.")
        return v

    def clean_quantity(self):
        v = self.cleaned_data.get('quantity')
        if v is not None and v <= 0:
            raise forms.ValidationError("Quantity must be a positive number.")
        return v

    def clean_date_needed(self):
        from datetime import date
        d = self.cleaned_data.get('date_needed')
        if d and d < date.today():
            raise forms.ValidationError("Date Needed cannot be in the past.")
        return d


# ── PLACE NEW ORDER FORMS ─────────────────────────────────────────────────────

class OrderDigitizingForm(_OrderQuoteValidationMixin, forms.ModelForm):
    class Meta:
        model  = OrderDigitizing
        fields = [
            'design_name', 'po_number',
            'width_mm', 'height_mm', 'size_unit',
            'colors', 'format', 'fabric', 'placement',
            'instructions', 'urgent', 'date_needed',
            'design_file', 'reference_file',
        ]
        widgets = {
            'urgent':      forms.CheckboxInput(),
            'date_needed': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False
        self.fields['design_name'].required = True


class OrderPatchesForm(_OrderQuoteValidationMixin, forms.ModelForm):
    class Meta:
        model  = OrderPatches
        fields = [
            'design_name', 'po_number',
            'width_mm', 'height_mm', 'size_unit',
            'colors', 'patch_type', 'backing',
            'quantity', 'embroidery_pct', 'thread_color',
            'instructions', 'urgent', 'date_needed',
            'design_file', 'reference_file',
        ]
        widgets = {
            'urgent':      forms.CheckboxInput(),
            'date_needed': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False
        self.fields['design_name'].required = True


class OrderVectorForm(_OrderQuoteValidationMixin, forms.ModelForm):
    class Meta:
        model  = OrderVector
        fields = [
            'design_name', 'po_number',
            'vector_format', 'background', 'colors',
            'instructions', 'urgent', 'date_needed',
            'design_file',
        ]
        widgets = {
            'urgent':      forms.CheckboxInput(),
            'date_needed': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False
        self.fields['design_name'].required = True


# ── ADD NEW QUOTE FORMS ───────────────────────────────────────────────────────

class QuoteDigitizingForm(_OrderQuoteValidationMixin, forms.ModelForm):
    class Meta:
        model  = QuoteDigitizing
        fields = [
            'design_name', 'po_number',
            'width_mm', 'height_mm', 'size_unit',
            'colors', 'fabric', 'placement',
            'description', 'urgent', 'date_needed',
            'design_file',
        ]
        widgets = {
            'urgent':      forms.CheckboxInput(),
            'date_needed': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False
        self.fields['design_name'].required = True


class QuotePatchesForm(_OrderQuoteValidationMixin, forms.ModelForm):
    class Meta:
        model  = QuotePatches
        fields = [
            'design_name', 'po_number',
            'width_mm', 'height_mm', 'size_unit',
            'colors', 'patch_type', 'backing',
            'quantity', 'embroidery_pct', 'thread_color',
            'description', 'urgent', 'date_needed',
            'design_file',
        ]
        widgets = {
            'urgent':      forms.CheckboxInput(),
            'date_needed': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False
        self.fields['design_name'].required = True


class QuoteVectorForm(_OrderQuoteValidationMixin, forms.ModelForm):
    class Meta:
        model  = QuoteVector
        fields = [
            'design_name', 'po_number',
            'vector_format', 'background', 'colors',
            'description', 'urgent', 'date_needed',
            'design_file',
        ]
        widgets = {
            'urgent':      forms.CheckboxInput(),
            'date_needed': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False
        self.fields['design_name'].required = True


# ── STAFF QUICK-EDIT FORMS (staff admin — status, price, preview file) ───────

class StaffOrderDigitizingForm(forms.ModelForm):
    class Meta:
        model  = OrderDigitizing
        fields = ['status', 'price', 'preview_file', 'design_file', 'admin_notes']


class StaffOrderPatchesForm(forms.ModelForm):
    class Meta:
        model  = OrderPatches
        fields = ['status', 'price', 'preview_file', 'design_file', 'admin_notes']


class StaffOrderVectorForm(forms.ModelForm):
    class Meta:
        model  = OrderVector
        fields = ['status', 'price', 'preview_file', 'design_file', 'admin_notes']


# ── STAFF QUOTE FORMS (staff admin — estimate cost, send quotation) ──────────

class StaffQuoteDigitizingForm(forms.ModelForm):
    class Meta:
        model  = QuoteDigitizing
        fields = ['status', 'quoted_price', 'preview_file', 'admin_notes']


class StaffQuotePatchesForm(forms.ModelForm):
    class Meta:
        model  = QuotePatches
        fields = ['status', 'quoted_price', 'preview_file', 'admin_notes']


class StaffQuoteVectorForm(forms.ModelForm):
    class Meta:
        model  = QuoteVector
        fields = ['status', 'quoted_price', 'preview_file', 'admin_notes']


# ── BILLING FORMS (staff admin) ───────────────────────────────────────────────

class BillingInvoiceForm(forms.ModelForm):
    class Meta:
        model  = BillingInvoice
        fields = [
            'user', 'invoice_number', 'invoice_date', 'due_date', 'status',
            'bill_to_name', 'bill_to_company', 'bill_to_address', 'bill_to_contact',
            'discount', 'tax_rate', 'shipping', 'notes',
        ]
        widgets = {
            'invoice_date':    forms.DateInput(attrs={'type': 'date'}),
            'due_date':        forms.DateInput(attrs={'type': 'date'}),
            'bill_to_address': forms.Textarea(attrs={'rows': 2}),
            'notes':           forms.Textarea(attrs={'rows': 2}),
        }


BillingInvoiceItemFormSet = inlineformset_factory(
    BillingInvoice, BillingInvoiceItem,
    fields=['description', 'qty', 'unit_price'],
    extra=3, can_delete=True,
)


class ProfileForm(forms.ModelForm):
    class Meta:
        model  = User
        fields = ['first_name', 'last_name', 'email', 'phone']
