from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Invoice, ContactMessage,
    OrderDigitizing, OrderPatches, OrderVector,
    QuoteDigitizing, QuotePatches, QuoteVector,
    OrderFile, QuoteFile,
    Order, Quote,
    BillingInvoice, BillingInvoiceItem,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display  = ('email', 'first_name', 'last_name', 'phone', 'is_staff', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name')
    ordering      = ('-date_joined',)


# ═══ PLACE NEW ORDER ══════════════════════════════════════════════════════════

@admin.register(OrderDigitizing)
class OrderDigitizingAdmin(admin.ModelAdmin):
    list_display    = ('pk', 'user', 'design_name', 'size_display', 'status', 'urgent', 'date_needed', 'created_at')
    list_filter     = ('status', 'urgent')
    search_fields   = ('design_name', 'user__email', 'po_number')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic',      {'fields': ('user', 'status', 'design_name', 'po_number', 'urgent', 'date_needed')}),
        ('Dimensions', {'fields': ('width_mm', 'height_mm', 'size_unit')}),
        ('Digitizing', {'fields': ('format', 'fabric', 'colors', 'placement', 'instructions')}),
        ('Files',      {'fields': ('design_file', 'reference_file')}),
        ('Pricing',    {'fields': ('price',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(OrderPatches)
class OrderPatchesAdmin(admin.ModelAdmin):
    list_display    = ('pk', 'user', 'design_name', 'size_display', 'quantity', 'status', 'urgent', 'date_needed', 'created_at')
    list_filter     = ('status', 'urgent')
    search_fields   = ('design_name', 'user__email', 'po_number')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic',      {'fields': ('user', 'status', 'design_name', 'po_number', 'urgent', 'date_needed')}),
        ('Dimensions', {'fields': ('width_mm', 'height_mm', 'size_unit')}),
        ('Patches',    {'fields': ('patch_type', 'backing', 'quantity', 'embroidery_pct', 'thread_color', 'colors')}),
        ('Notes',      {'fields': ('instructions',)}),
        ('Files',      {'fields': ('design_file', 'reference_file')}),
        ('Pricing',    {'fields': ('price',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(OrderVector)
class OrderVectorAdmin(admin.ModelAdmin):
    list_display    = ('pk', 'user', 'design_name', 'vector_format', 'status', 'urgent', 'date_needed', 'created_at')
    list_filter     = ('status', 'urgent')
    search_fields   = ('design_name', 'user__email', 'po_number')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic',      {'fields': ('user', 'status', 'design_name', 'po_number', 'urgent', 'date_needed')}),
        ('Vector',     {'fields': ('vector_format', 'background', 'colors')}),
        ('Notes',      {'fields': ('instructions',)}),
        ('Files',      {'fields': ('design_file',)}),
        ('Pricing',    {'fields': ('price',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


# ═══ ADD NEW QUOTE ═════════════════════════════════════════════════════════════

@admin.register(QuoteDigitizing)
class QuoteDigitizingAdmin(admin.ModelAdmin):
    list_display    = ('pk', 'user', 'design_name', 'size_display', 'status', 'quoted_price', 'urgent', 'date_needed', 'created_at')
    list_filter     = ('status', 'urgent')
    search_fields   = ('design_name', 'user__email', 'po_number')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic',      {'fields': ('user', 'status', 'design_name', 'po_number', 'urgent', 'date_needed')}),
        ('Dimensions', {'fields': ('width_mm', 'height_mm', 'size_unit')}),
        ('Digitizing', {'fields': ('fabric', 'colors', 'placement', 'description')}),
        ('Files',      {'fields': ('design_file',)}),
        ('Pricing',    {'fields': ('quoted_price', 'admin_notes')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(QuotePatches)
class QuotePatchesAdmin(admin.ModelAdmin):
    list_display    = ('pk', 'user', 'design_name', 'size_display', 'quantity', 'status', 'quoted_price', 'urgent', 'date_needed', 'created_at')
    list_filter     = ('status', 'urgent')
    search_fields   = ('design_name', 'user__email', 'po_number')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic',      {'fields': ('user', 'status', 'design_name', 'po_number', 'urgent', 'date_needed')}),
        ('Dimensions', {'fields': ('width_mm', 'height_mm', 'size_unit')}),
        ('Patches',    {'fields': ('patch_type', 'backing', 'quantity', 'embroidery_pct', 'thread_color', 'colors')}),
        ('Notes',      {'fields': ('description',)}),
        ('Files',      {'fields': ('design_file',)}),
        ('Pricing',    {'fields': ('quoted_price', 'admin_notes')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(QuoteVector)
class QuoteVectorAdmin(admin.ModelAdmin):
    list_display    = ('pk', 'user', 'design_name', 'vector_format', 'status', 'quoted_price', 'urgent', 'date_needed', 'created_at')
    list_filter     = ('status', 'urgent')
    search_fields   = ('design_name', 'user__email', 'po_number')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic',      {'fields': ('user', 'status', 'design_name', 'po_number', 'urgent', 'date_needed')}),
        ('Vector',     {'fields': ('vector_format', 'background', 'colors')}),
        ('Notes',      {'fields': ('description',)}),
        ('Files',      {'fields': ('design_file',)}),
        ('Pricing',    {'fields': ('quoted_price', 'admin_notes')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


# ═══ LEGACY ════════════════════════════════════════════════════════════════════

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ('pk', 'user', 'order_type', 'design_name', 'size_display', 'status', 'urgent', 'date_needed', 'created_at')
    list_filter     = ('order_type', 'status', 'urgent')
    search_fields   = ('design_name', 'user__email', 'po_number')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display    = ('pk', 'user', 'quote_type', 'design_name', 'size_display', 'status', 'quoted_price', 'urgent', 'date_needed', 'created_at')
    list_filter     = ('quote_type', 'status', 'urgent')
    search_fields   = ('design_name', 'user__email', 'po_number')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display  = ('invoice_number', 'user', 'order', 'amount', 'status', 'due_date', 'created_at')
    list_filter   = ('status',)
    search_fields = ('invoice_number', 'user__email')


# ═══ BILLING ═══════════════════════════════════════════════════════════════════

class BillingInvoiceItemInline(admin.TabularInline):
    model = BillingInvoiceItem
    extra = 3
    fields = ('description', 'qty', 'unit_price')


@admin.register(BillingInvoice)
class BillingInvoiceAdmin(admin.ModelAdmin):
    list_display    = ('invoice_number', 'user', 'bill_to_company', 'invoice_date', 'due_date', 'status', 'subtotal', 'balance_due')
    list_filter     = ('status',)
    search_fields   = ('invoice_number', 'user__email', 'bill_to_name', 'bill_to_company')
    readonly_fields = ('created_at', 'updated_at')
    inlines         = [BillingInvoiceItemInline]
    fieldsets = (
        ('Invoice',   {'fields': ('user', 'invoice_number', 'invoice_date', 'due_date', 'status')}),
        ('Bill To',   {'fields': ('bill_to_name', 'bill_to_company', 'bill_to_address', 'bill_to_contact')}),
        ('Linked source', {'fields': ('content_type', 'object_id')}),
        ('Totals',    {'fields': ('discount', 'tax_rate', 'shipping')}),
        ('Other',     {'fields': ('paid_at', 'notes')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display  = ('first_name', 'last_name', 'email', 'phone', 'service', 'created_at')
    search_fields = ('email', 'first_name', 'last_name')


@admin.register(OrderFile)
class OrderFileAdmin(admin.ModelAdmin):
    list_display = ('pk', 'content_type', 'object_id', 'file', 'uploaded_at')
    list_filter  = ('content_type',)


@admin.register(QuoteFile)
class QuoteFileAdmin(admin.ModelAdmin):
    list_display = ('pk', 'content_type', 'object_id', 'file', 'uploaded_at')
    list_filter  = ('content_type',)
