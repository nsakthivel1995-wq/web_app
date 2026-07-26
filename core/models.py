from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class User(AbstractUser):
    phone = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"


# ── SHARED CHOICES ─────────────────────────────────────────────────────────────

UNIT_CHOICES = [
    ('in', 'Inches'),
    ('cm', 'CM'),
    ('mm', 'MM'),
]

FORMAT_CHOICES = [
    ('DST', 'DST'), ('PES', 'PES'), ('EXP', 'EXP'),
    ('JEF', 'JEF'), ('VP3', 'VP3'), ('EMB', 'EMB'), ('XXX', 'XXX'), ('OTHER', 'Other'),
]

# ── UNIFIED WORKFLOW STATUS ─────────────────────────────────────────────────
# Same status pipeline drives every Order and every Quote table, matching the
# submission → quote → confirm → design → review → correct → pay → download
# workflow. WORKFLOW_STAGE_ORDER is the "happy path" sequence used to render
# progress bars; 'rejected' is a terminal side-branch off 'quote_sent'.

WORKFLOW_STATUS_CHOICES = [
    ('submitted',            'Submitted'),
    ('quote_sent',           'Quote Sent'),
    ('confirmed',            'Confirmed'),
    ('design_started',       'Design Started'),
    ('in_progress',          'In Progress'),
    ('completed',            'Completed'),
    ('client_review',        'Client Review'),
    ('correction_requested', 'Correction Requested'),
    ('correction_completed', 'Correction Completed'),
    ('payment_pending',      'Payment Pending'),
    ('payment_completed',    'Payment Completed'),
    ('invoice_generated',    'Invoice Generated'),
    ('download_available',   'Download Available'),
    ('rejected',             'Rejected'),
]

WORKFLOW_STAGE_ORDER = [k for k, _ in WORKFLOW_STATUS_CHOICES if k != 'rejected']

# Kept as aliases so any old code/templates referencing these names still work.
ORDER_STATUS_CHOICES = WORKFLOW_STATUS_CHOICES
QUOTE_STATUS_CHOICES = WORKFLOW_STATUS_CHOICES

DOWNLOAD_UNLOCKED_STATUSES = ('download_available',)
CORRECTION_ELIGIBLE_STATUSES = ('completed', 'client_review', 'correction_completed')


class WorkflowMixin:
    """Shared helpers for the 6 Order/Quote models — status pipeline, client
    actions, and the preview/original file lock described in the workflow."""

    def stage_index(self):
        try:
            return WORKFLOW_STAGE_ORDER.index(self.status)
        except ValueError:
            return -1

    def stage_progress_pct(self):
        idx = self.stage_index()
        if idx < 0:
            return 0
        return int(round((idx / (len(WORKFLOW_STAGE_ORDER) - 1)) * 100))

    @property
    def is_download_unlocked(self):
        return self.status in DOWNLOAD_UNLOCKED_STATUSES

    @property
    def client_can_request_correction(self):
        return self.status in CORRECTION_ELIGIBLE_STATUSES

    @property
    def client_can_pay(self):
        return self.status == 'payment_pending'

    @property
    def client_can_respond_to_quote(self):
        return self.status == 'quote_sent'

    def status_badge_class(self):
        if self.status == 'rejected':
            return 'badge-rej'
        if self.status in ('correction_requested', 'payment_pending'):
            return 'badge-warn'
        if self.status in ('completed', 'client_review', 'correction_completed',
                            'payment_completed', 'invoice_generated', 'download_available'):
            return 'badge-ok'
        if self.status == 'submitted':
            return 'badge-new'
        return 'badge-pend'


# ═══════════════════════════════════════════════════════════════════════════════
#  PLACE NEW ORDER — 3 separate tables
# ═══════════════════════════════════════════════════════════════════════════════

class OrderDigitizing(WorkflowMixin, models.Model):
    """PLACE NEW ORDER → Digitizing order"""
    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_digitizing')
    status          = models.CharField(max_length=25, choices=WORKFLOW_STATUS_CHOICES, default='submitted')
    design_name     = models.CharField(max_length=200)
    po_number       = models.CharField(max_length=100, blank=True)
    width_mm        = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    height_mm       = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    size_unit       = models.CharField(max_length=5, choices=UNIT_CHOICES, default='in', blank=True)
    format          = models.CharField(max_length=10, choices=FORMAT_CHOICES, blank=True)
    fabric          = models.CharField(max_length=100, blank=True)
    colors          = models.PositiveIntegerField(null=True, blank=True)
    placement       = models.CharField(max_length=100, blank=True)
    instructions    = models.TextField(blank=True)
    urgent          = models.BooleanField(default=False)
    date_needed     = models.DateField(null=True, blank=True)
    design_file     = models.FileField(upload_to='orders/digitizing/designs/', null=True, blank=True)
    reference_file  = models.FileField(upload_to='orders/digitizing/references/', null=True, blank=True)
    preview_file    = models.FileField(upload_to='orders/digitizing/previews/', null=True, blank=True)
    price           = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    admin_notes     = models.TextField(blank=True)
    client_notes    = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Order – Digitizing'
        verbose_name_plural = 'Orders – Digitizing'

    def size_display(self):
        if self.width_mm and self.height_mm:
            return f"{self.width_mm} × {self.height_mm} {self.size_unit or 'in'}"
        return "—"

    def __str__(self):
        return f"Digitizing Order #{self.pk} — {self.design_name}"


class OrderPatches(WorkflowMixin, models.Model):
    """PLACE NEW ORDER → Patches order"""
    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_patches')
    status          = models.CharField(max_length=25, choices=WORKFLOW_STATUS_CHOICES, default='submitted')
    design_name     = models.CharField(max_length=200)
    po_number       = models.CharField(max_length=100, blank=True)
    width_mm        = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    height_mm       = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    size_unit       = models.CharField(max_length=5, choices=UNIT_CHOICES, default='in', blank=True)
    colors          = models.PositiveIntegerField(null=True, blank=True)
    patch_type      = models.CharField(max_length=100, blank=True)
    backing         = models.CharField(max_length=100, blank=True)
    quantity        = models.PositiveIntegerField(null=True, blank=True)
    embroidery_pct  = models.CharField(max_length=10, blank=True)
    thread_color    = models.TextField(blank=True)
    instructions    = models.TextField(blank=True)
    urgent          = models.BooleanField(default=False)
    date_needed     = models.DateField(null=True, blank=True)
    design_file     = models.FileField(upload_to='orders/patches/designs/', null=True, blank=True)
    reference_file  = models.FileField(upload_to='orders/patches/references/', null=True, blank=True)
    preview_file    = models.FileField(upload_to='orders/patches/previews/', null=True, blank=True)
    price           = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    admin_notes     = models.TextField(blank=True)
    client_notes    = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Order – Patches'
        verbose_name_plural = 'Orders – Patches'

    def size_display(self):
        if self.width_mm and self.height_mm:
            return f"{self.width_mm} × {self.height_mm} {self.size_unit or 'in'}"
        return "—"

    def __str__(self):
        return f"Patches Order #{self.pk} — {self.design_name}"


class OrderVector(WorkflowMixin, models.Model):
    """PLACE NEW ORDER → Vector order"""
    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_vector')
    status          = models.CharField(max_length=25, choices=WORKFLOW_STATUS_CHOICES, default='submitted')
    design_name     = models.CharField(max_length=200)
    po_number       = models.CharField(max_length=100, blank=True)
    vector_format   = models.CharField(max_length=50, blank=True)
    background      = models.CharField(max_length=50, blank=True)
    colors          = models.PositiveIntegerField(null=True, blank=True)
    instructions    = models.TextField(blank=True)
    urgent          = models.BooleanField(default=False)
    date_needed     = models.DateField(null=True, blank=True)
    design_file     = models.FileField(upload_to='orders/vector/designs/', null=True, blank=True)
    preview_file    = models.FileField(upload_to='orders/vector/previews/', null=True, blank=True)
    price           = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    admin_notes     = models.TextField(blank=True)
    client_notes    = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Order – Vector'
        verbose_name_plural = 'Orders – Vector'

    def __str__(self):
        return f"Vector Order #{self.pk} — {self.design_name}"


# ═══════════════════════════════════════════════════════════════════════════════
#  ADD NEW QUOTE — 3 separate tables
# ═══════════════════════════════════════════════════════════════════════════════

class QuoteDigitizing(WorkflowMixin, models.Model):
    """ADD NEW QUOTE → Digitizing order"""
    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quotes_digitizing')
    status          = models.CharField(max_length=25, choices=WORKFLOW_STATUS_CHOICES, default='submitted')
    design_name     = models.CharField(max_length=200)
    po_number       = models.CharField(max_length=100, blank=True)
    width_mm        = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    height_mm       = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    size_unit       = models.CharField(max_length=5, choices=UNIT_CHOICES, default='in', blank=True)
    fabric          = models.CharField(max_length=100, blank=True)
    colors          = models.PositiveIntegerField(null=True, blank=True)
    placement       = models.CharField(max_length=100, blank=True)
    description     = models.TextField(blank=True)
    urgent          = models.BooleanField(default=False)
    date_needed     = models.DateField(null=True, blank=True)
    design_file     = models.FileField(upload_to='quotes/digitizing/designs/', null=True, blank=True)
    preview_file    = models.FileField(upload_to='quotes/digitizing/previews/', null=True, blank=True)
    quoted_price    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    admin_notes     = models.TextField(blank=True)
    client_notes    = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Quote – Digitizing'
        verbose_name_plural = 'Quotes – Digitizing'

    def size_display(self):
        if self.width_mm and self.height_mm:
            return f"{self.width_mm} × {self.height_mm} {self.size_unit or 'in'}"
        return "—"

    def __str__(self):
        return f"Digitizing Quote #{self.pk} — {self.design_name}"


class QuotePatches(WorkflowMixin, models.Model):
    """ADD NEW QUOTE → Patches order"""
    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quotes_patches')
    status          = models.CharField(max_length=25, choices=WORKFLOW_STATUS_CHOICES, default='submitted')
    design_name     = models.CharField(max_length=200)
    po_number       = models.CharField(max_length=100, blank=True)
    width_mm        = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    height_mm       = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    size_unit       = models.CharField(max_length=5, choices=UNIT_CHOICES, default='in', blank=True)
    colors          = models.PositiveIntegerField(null=True, blank=True)
    patch_type      = models.CharField(max_length=100, blank=True)
    backing         = models.CharField(max_length=100, blank=True)
    quantity        = models.PositiveIntegerField(null=True, blank=True)
    embroidery_pct  = models.CharField(max_length=10, blank=True)
    thread_color    = models.TextField(blank=True)
    description     = models.TextField(blank=True)
    urgent          = models.BooleanField(default=False)
    date_needed     = models.DateField(null=True, blank=True)
    design_file     = models.FileField(upload_to='quotes/patches/designs/', null=True, blank=True)
    preview_file    = models.FileField(upload_to='quotes/patches/previews/', null=True, blank=True)
    quoted_price    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    admin_notes     = models.TextField(blank=True)
    client_notes    = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Quote – Patches'
        verbose_name_plural = 'Quotes – Patches'

    def size_display(self):
        if self.width_mm and self.height_mm:
            return f"{self.width_mm} × {self.height_mm} {self.size_unit or 'in'}"
        return "—"

    def __str__(self):
        return f"Patches Quote #{self.pk} — {self.design_name}"


class QuoteVector(WorkflowMixin, models.Model):
    """ADD NEW QUOTE → Vector order"""
    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quotes_vector')
    status          = models.CharField(max_length=25, choices=WORKFLOW_STATUS_CHOICES, default='submitted')
    design_name     = models.CharField(max_length=200)
    po_number       = models.CharField(max_length=100, blank=True)
    vector_format   = models.CharField(max_length=50, blank=True)
    background      = models.CharField(max_length=50, blank=True)
    colors          = models.PositiveIntegerField(null=True, blank=True)
    description     = models.TextField(blank=True)
    urgent          = models.BooleanField(default=False)
    date_needed     = models.DateField(null=True, blank=True)
    design_file     = models.FileField(upload_to='quotes/vector/designs/', null=True, blank=True)
    preview_file    = models.FileField(upload_to='quotes/vector/previews/', null=True, blank=True)
    quoted_price    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    admin_notes     = models.TextField(blank=True)
    client_notes    = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Quote – Vector'
        verbose_name_plural = 'Quotes – Vector'

    def __str__(self):
        return f"Vector Quote #{self.pk} — {self.design_name}"


# ═══════════════════════════════════════════════════════════════════════════════
#  EXTRA FILES — supports uploading more than one design/reference file per
#  order or quote (the "+" button on the dashboard). Each order/quote model
#  keeps its own single design_file/reference_file for the FIRST upload; any
#  additional files selected are stored here instead of being silently dropped.
# ═══════════════════════════════════════════════════════════════════════════════

class OrderFile(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id    = models.PositiveIntegerField()
    order        = GenericForeignKey('content_type', 'object_id')
    file         = models.FileField(upload_to='orders/extra_files/')
    uploaded_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f"OrderFile #{self.pk} — {self.file.name}"


class QuoteFile(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id    = models.PositiveIntegerField()
    quote        = GenericForeignKey('content_type', 'object_id')
    file         = models.FileField(upload_to='quotes/extra_files/')
    uploaded_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f"QuoteFile #{self.pk} — {self.file.name}"


# ═══════════════════════════════════════════════════════════════════════════════
#  LEGACY MODELS (kept for backward-compatibility / data migration)
# ═══════════════════════════════════════════════════════════════════════════════

class Order(models.Model):
    """Legacy single-table order — kept for existing data."""
    ORDER_TYPES = [
        ('digitizing', 'Embroidery Digitizing'),
        ('patches', 'Patches'),
        ('vector', 'Vector Art'),
    ]
    STATUS_CHOICES = ORDER_STATUS_CHOICES
    FORMAT_CHOICES = FORMAT_CHOICES
    UNIT_CHOICES   = UNIT_CHOICES

    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    order_type      = models.CharField(max_length=20, choices=ORDER_TYPES)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    design_name     = models.CharField(max_length=200)
    po_number       = models.CharField(max_length=100, blank=True)
    width_mm        = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    height_mm       = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    size_unit       = models.CharField(max_length=5, choices=UNIT_CHOICES, default='in', blank=True)
    format          = models.CharField(max_length=10, choices=FORMAT_CHOICES, blank=True)
    fabric          = models.CharField(max_length=100, blank=True)
    colors          = models.PositiveIntegerField(null=True, blank=True)
    placement       = models.CharField(max_length=100, blank=True)
    instructions    = models.TextField(blank=True)
    urgent          = models.BooleanField(default=False)
    date_needed     = models.DateField(null=True, blank=True)
    design_file     = models.FileField(upload_to='orders/designs/', null=True, blank=True)
    reference_file  = models.FileField(upload_to='orders/references/', null=True, blank=True)
    patch_type      = models.CharField(max_length=100, blank=True)
    quantity        = models.PositiveIntegerField(null=True, blank=True)
    backing         = models.CharField(max_length=100, blank=True)
    thread_color    = models.TextField(blank=True)
    embroidery_pct  = models.CharField(max_length=10, blank=True)
    vector_format   = models.CharField(max_length=50, blank=True)
    background      = models.CharField(max_length=50, blank=True)
    price           = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '[Legacy] Order'
        verbose_name_plural = '[Legacy] Orders'

    def size_display(self):
        if self.width_mm and self.height_mm:
            return f"{self.width_mm} × {self.height_mm} {self.size_unit or 'in'}"
        return "—"

    def __str__(self):
        return f"[Legacy] Order #{self.pk} — {self.design_name}"


class Quote(models.Model):
    """Legacy single-table quote — kept for existing data."""
    QUOTE_TYPES    = [
        ('digitizing', 'Embroidery Digitizing'),
        ('patches', 'Patches'),
        ('vector', 'Vector Art'),
    ]
    STATUS_CHOICES = QUOTE_STATUS_CHOICES
    UNIT_CHOICES   = UNIT_CHOICES

    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quotes')
    quote_type      = models.CharField(max_length=20, choices=QUOTE_TYPES)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    design_name     = models.CharField(max_length=200)
    po_number       = models.CharField(max_length=100, blank=True)
    width_mm        = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    height_mm       = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    size_unit       = models.CharField(max_length=5, choices=UNIT_CHOICES, default='in', blank=True)
    fabric          = models.CharField(max_length=100, blank=True)
    colors          = models.PositiveIntegerField(null=True, blank=True)
    placement       = models.CharField(max_length=100, blank=True)
    description     = models.TextField(blank=True)
    urgent          = models.BooleanField(default=False)
    date_needed     = models.DateField(null=True, blank=True)
    design_file     = models.FileField(upload_to='quotes/designs/', null=True, blank=True)
    patch_type      = models.CharField(max_length=100, blank=True)
    quantity        = models.PositiveIntegerField(null=True, blank=True)
    backing         = models.CharField(max_length=100, blank=True)
    thread_color    = models.TextField(blank=True)
    embroidery_pct  = models.CharField(max_length=10, blank=True)
    vector_format   = models.CharField(max_length=50, blank=True)
    background      = models.CharField(max_length=50, blank=True)
    quoted_price    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    admin_notes     = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '[Legacy] Quote'
        verbose_name_plural = '[Legacy] Quotes'

    def size_display(self):
        if self.width_mm and self.height_mm:
            return f"{self.width_mm} × {self.height_mm} {self.size_unit or 'in'}"
        return "—"

    def __str__(self):
        return f"[Legacy] Quote #{self.pk} — {self.design_name}"


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('uninvoiced', 'Uninvoiced'),
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    ]

    user           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices')
    order          = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
    invoice_number = models.CharField(max_length=50, unique=True)
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uninvoiced')
    amount         = models.DecimalField(max_digits=10, decimal_places=2)
    description    = models.TextField(blank=True)
    due_date       = models.DateField(null=True, blank=True)
    paid_at        = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Invoice {self.invoice_number} — Rs.{self.amount}"


# ═══════════════════════════════════════════════════════════════════════════════
#  BILLING — invoice generated from any of the 6 order/quote tables
#  (mirrors the rsd_temp.xlsx invoice template: BILL TO block, invoice
#  no/date/due date, line-items table, and a totals block)
# ═══════════════════════════════════════════════════════════════════════════════

BILLING_STATUS_CHOICES = [
    ('unpaid', 'Unpaid'),
    ('paid', 'Paid'),
]


PAYMENT_METHOD_CHOICES = [
    ('razorpay', 'Razorpay'),
    ('stripe',   'Stripe'),
    ('paypal',   'PayPal'),
    ('upi',      'UPI'),
]


class BillingInvoice(models.Model):
    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='billing_invoices')
    invoice_number   = models.CharField(max_length=50, unique=True)
    invoice_date     = models.DateField()
    due_date         = models.DateField(null=True, blank=True)
    status           = models.CharField(max_length=10, choices=BILLING_STATUS_CHOICES, default='unpaid')
    payment_method   = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, blank=True)

    # BILL TO block
    bill_to_name     = models.CharField('Contact Name', max_length=150, blank=True)
    bill_to_company  = models.CharField('Client Company Name', max_length=200, blank=True)
    bill_to_address  = models.TextField('Address', blank=True)
    bill_to_contact  = models.CharField('Phone / Email', max_length=150, blank=True)

    # Linked source order/quote (any of the 6 tables), same generic pattern as OrderFile/QuoteFile
    content_type     = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id        = models.PositiveIntegerField(null=True, blank=True)
    linked_item      = GenericForeignKey('content_type', 'object_id')

    # Totals block
    discount         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_rate         = models.DecimalField('Tax Rate (%)', max_digits=5, decimal_places=2, default=0)
    shipping         = models.DecimalField('Shipping / Handling', max_digits=10, decimal_places=2, default=0)

    paid_at          = models.DateTimeField(null=True, blank=True)
    notes            = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Billing Invoice'
        verbose_name_plural = 'Billing Invoices'

    def __str__(self):
        return f"{self.invoice_number} — {self.user}"

    def subtotal(self):
        total = 0
        for i in self.items.all():
            total += i.total()
        return total

    def subtotal_less_discount(self):
        return self.subtotal() - (self.discount or 0)

    def total_tax(self):
        return (self.subtotal_less_discount() * (self.tax_rate or 0)) / 100

    def balance_due(self):
        return self.subtotal_less_discount() + self.total_tax() + (self.shipping or 0)


class BillingInvoiceItem(models.Model):
    invoice     = models.ForeignKey(BillingInvoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255)
    qty         = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price  = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ['pk']

    def total(self):
        return (self.qty or 0) * (self.unit_price or 0)

    def __str__(self):
        return f"{self.description} × {self.qty}"


class ContactMessage(models.Model):
    SERVICE_CHOICES = [
        ('Logo Digitizing', 'Logo Digitizing'),
        ('3D Puff Embroidery', '3D Puff Embroidery'),
        ('Cap Digitizing', 'Cap Digitizing'),
        ('Screen Printing', 'Screen Printing'),
        ('Vinyl Cutting / HTV', 'Vinyl Cutting / HTV'),
        ('Digital Printing & Stickers', 'Digital Printing & Stickers'),
        ('Corporate Uniforms', 'Corporate Uniforms'),
        ('Sports Uniforms', 'Sports Uniforms'),
        ('Custom Design Work', 'Custom Design Work'),
        ('Other', 'Other'),
    ]

    first_name = models.CharField(max_length=100)
    last_name  = models.CharField(max_length=100)
    email      = models.EmailField()
    phone      = models.CharField(max_length=15)
    service    = models.CharField(max_length=100, choices=SERVICE_CHOICES)
    message    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} — {self.service} ({self.email})"
