from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from .models import (
    User, Invoice, ContactMessage,
    OrderDigitizing, OrderPatches, OrderVector,
    QuoteDigitizing, QuotePatches, QuoteVector,
    OrderFile, QuoteFile,
    Order, Quote,   # legacy — dashboard still shows them
    BillingInvoice, BillingInvoiceItem,
    PAYMENT_METHOD_CHOICES,
)
from .forms import (
    RegisterForm, LoginForm,
    OrderDigitizingForm, OrderPatchesForm, OrderVectorForm,
    QuoteDigitizingForm, QuotePatchesForm, QuoteVectorForm,
    ProfileForm,
    BillingInvoiceForm, BillingInvoiceItemFormSet,
    StaffOrderDigitizingForm, StaffOrderPatchesForm, StaffOrderVectorForm,
    StaffQuoteDigitizingForm, StaffQuotePatchesForm, StaffQuoteVectorForm,
)

staff_required = user_passes_test(lambda u: u.is_authenticated and u.is_staff, login_url='/auth/')


# ─── PUBLIC PAGES ─────────────────────────────────────────────────────────────

def index(request):
    return render(request, 'index.html', {'user': request.user})


# ─── AUTH ─────────────────────────────────────────────────────────────────────

def auth_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    login_form    = LoginForm()
    register_form = RegisterForm()
    panel         = 'login'
    errors        = {}

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'login':
            panel    = 'login'
            email    = request.POST.get('username', '').strip().lower()
            password = request.POST.get('password', '')
            user     = authenticate(request, username=email, password=password)
            if user is None:
                try:
                    u    = User.objects.get(email=email)
                    user = authenticate(request, username=u.username, password=password)
                except User.DoesNotExist:
                    user = None
            if user:
                login(request, user)
                return redirect('dashboard')
            else:
                errors['login'] = 'Invalid email or password. Please try again.'

        elif action == 'register':
            panel         = 'register'
            register_form = RegisterForm(request.POST)
            if register_form.is_valid():
                user = register_form.save()
                login(request, user)
                messages.success(request, f"Welcome, {user.first_name}! Your account has been created.")
                return redirect('dashboard')
            else:
                err_list = []
                for field, errs in register_form.errors.items():
                    for e in errs:
                        err_list.append(e if field == '__all__' else str(e))
                errors['register'] = ' '.join(err_list)

    return render(request, 'auth.html', {
        'login_form':    login_form,
        'register_form': register_form,
        'panel':         panel,
        'errors':        errors,
    })


def contact_submit(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name',  '').strip()
        email      = request.POST.get('email',      '').strip()
        phone      = request.POST.get('phone',      '').replace(' ', '')
        service    = request.POST.get('service',    '').strip()
        message    = request.POST.get('message',    '').strip()

        errors = []
        if not first_name: errors.append('First name is required.')
        if not last_name:  errors.append('Last name is required.')
        if not email:      errors.append('Email is required.')
        if not phone.isdigit() or len(phone) != 10:
            errors.append('Phone must be exactly 10 digits.')
        if not service: errors.append('Please select a service.')
        if not message: errors.append('Project details are required.')

        if errors:
            return JsonResponse({'success': False, 'errors': errors}, status=400)

        ContactMessage.objects.create(
            first_name=first_name, last_name=last_name,
            email=email, phone=phone, service=service, message=message,
        )
        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'errors': ['Invalid request.']}, status=400)


def logout_view(request):
    logout(request)
    return redirect('index')


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

def _save_extra_files(request, obj, FileModel, field_name='design_file'):
    """
    The '+' button lets people attach more than one file, but each
    order/quote model only has a single FileField. Django binds just ONE of
    the uploaded files to that field (the last one in the list) and silently
    drops the rest. This saves every additional file so nothing is lost.
    """
    files = request.FILES.getlist(field_name)
    if len(files) <= 1:
        return
    extra_files = files[:-1]  # the last one was already bound to the model's FileField
    content_type = ContentType.objects.get_for_model(obj)
    for f in extra_files:
        FileModel.objects.create(content_type=content_type, object_id=obj.pk, file=f)


def _attach_extra_files(queryset, FileModel):
    """Attach an `.extra_files` list (from OrderFile/QuoteFile) to each object
    in queryset, so templates can link to every uploaded file, not just the
    one bound to the model's single FileField."""
    objs = list(queryset)
    if not objs:
        return objs
    content_type = ContentType.objects.get_for_model(objs[0])
    pks = [o.pk for o in objs]
    extras = FileModel.objects.filter(content_type=content_type, object_id__in=pks)
    grouped = {}
    for ef in extras:
        grouped.setdefault(ef.object_id, []).append(ef)
    for o in objs:
        o.extra_files = grouped.get(o.pk, [])
    return objs


def _attach_invoices(objs):
    """Attach a `.invoice` attribute (BillingInvoice or None) to each object
    in objs, matched via the invoice's generic content_type/object_id link,
    so the downloads tab can show an invoice/receipt next to each order."""
    if not objs:
        return objs
    content_type = ContentType.objects.get_for_model(objs[0])
    pks = [o.pk for o in objs]
    invoices = BillingInvoice.objects.filter(content_type=content_type, object_id__in=pks)
    grouped = {inv.object_id: inv for inv in invoices}
    for o in objs:
        o.invoice = grouped.get(o.pk)
    return objs


FINISHED_ORDER_STATUSES = ('download_available',)
ACTIVE_ORDER_STATUSES = ('confirmed', 'design_started', 'in_progress', 'completed',
                          'client_review', 'correction_requested', 'correction_completed')
PENDING_QUOTE_STATUSES = ('submitted',)


def _collect_uploads(objs, target_key, label):
    """Flatten design/reference/extra files from a list of order or quote
    objects into a unified row list for the client Uploads tab."""
    rows = []
    for o in objs:
        if getattr(o, 'design_file', None):
            rows.append({
                'target': target_key, 'pk': o.pk, 'label': label,
                'design_name': getattr(o, 'design_name', ''),
                'file_url': o.design_file.url,
                'file_name': o.design_file.name.rsplit('/', 1)[-1],
                'uploaded_at': o.created_at, 'kind': 'Design file',
            })
        ref = getattr(o, 'reference_file', None)
        if ref:
            rows.append({
                'target': target_key, 'pk': o.pk, 'label': label,
                'design_name': getattr(o, 'design_name', ''),
                'file_url': ref.url,
                'file_name': ref.name.rsplit('/', 1)[-1],
                'uploaded_at': o.created_at, 'kind': 'Reference file',
            })
        for ef in getattr(o, 'extra_files', []):
            rows.append({
                'target': target_key, 'pk': o.pk, 'label': label,
                'design_name': getattr(o, 'design_name', ''),
                'file_url': ef.file.url,
                'file_name': ef.file.name.rsplit('/', 1)[-1],
                'uploaded_at': ef.uploaded_at, 'kind': 'Extra file',
            })
    return rows


@login_required(login_url='/auth/')
def dashboard(request):
    user = request.user

    # New separate-table queries
    qs_orders_digitizing = OrderDigitizing.objects.filter(user=user)
    qs_orders_patches    = OrderPatches.objects.filter(user=user)
    qs_orders_vector     = OrderVector.objects.filter(user=user)
    qs_quotes_digitizing = QuoteDigitizing.objects.filter(user=user)
    qs_quotes_patches    = QuotePatches.objects.filter(user=user)
    qs_quotes_vector     = QuoteVector.objects.filter(user=user)

    # Legacy (for backward compat display)
    legacy_orders  = Order.objects.filter(user=user)
    legacy_quotes  = Quote.objects.filter(user=user)
    invoices       = Invoice.objects.filter(user=user)
    billing_invoices = BillingInvoice.objects.filter(user=user).prefetch_related('items')

    total_orders  = (qs_orders_digitizing.count() + qs_orders_patches.count() +
                     qs_orders_vector.count() + legacy_orders.count())
    active_orders = (
        qs_orders_digitizing.filter(status__in=ACTIVE_ORDER_STATUSES).count() +
        qs_orders_patches.filter(status__in=ACTIVE_ORDER_STATUSES).count() +
        qs_orders_vector.filter(status__in=ACTIVE_ORDER_STATUSES).count() +
        legacy_orders.filter(status__in=ACTIVE_ORDER_STATUSES).count()
    )
    total_quotes   = (qs_quotes_digitizing.count() + qs_quotes_patches.count() +
                      qs_quotes_vector.count() + legacy_quotes.count())
    pending_quotes = (
        qs_quotes_digitizing.filter(status__in=PENDING_QUOTE_STATUSES).count() +
        qs_quotes_patches.filter(status__in=PENDING_QUOTE_STATUSES).count() +
        qs_quotes_vector.filter(status__in=PENDING_QUOTE_STATUSES).count() +
        legacy_quotes.filter(status='pending').count()
    )
    downloads_ready = (
        qs_orders_digitizing.filter(status__in=FINISHED_ORDER_STATUSES).count() +
        qs_orders_patches.filter(status__in=FINISHED_ORDER_STATUSES).count() +
        qs_orders_vector.filter(status__in=FINISHED_ORDER_STATUSES).count()
    )

    stats = {
        'total_orders':    total_orders,
        'active_orders':   active_orders,
        'total_quotes':    total_quotes,
        'pending_quotes':  pending_quotes,
        'unpaid_invoices': invoices.filter(status='unpaid').count(),
        'downloads_ready': downloads_ready,
    }

    # Attach extra uploaded files for display (converts querysets to lists)
    orders_digitizing = _attach_extra_files(qs_orders_digitizing, OrderFile)
    orders_patches    = _attach_extra_files(qs_orders_patches, OrderFile)
    orders_vector     = _attach_extra_files(qs_orders_vector, OrderFile)
    quotes_digitizing = _attach_extra_files(qs_quotes_digitizing, QuoteFile)
    quotes_patches    = _attach_extra_files(qs_quotes_patches, QuoteFile)
    quotes_vector     = _attach_extra_files(qs_quotes_vector, QuoteFile)

    # Attach any linked billing invoice to each order (for the Downloads tab)
    _attach_invoices(orders_digitizing)
    _attach_invoices(orders_patches)
    _attach_invoices(orders_vector)

    # Final-file downloads: orders that are completed/delivered, with their
    # design files, extra files, and (if generated) invoice/receipt links
    downloads_digitizing = [o for o in orders_digitizing if o.status in FINISHED_ORDER_STATUSES]
    downloads_patches    = [o for o in orders_patches    if o.status in FINISHED_ORDER_STATUSES]
    downloads_vector     = [o for o in orders_vector     if o.status in FINISHED_ORDER_STATUSES]

    # All files the client has ever sent, across every order/quote table
    all_uploads = (
        _collect_uploads(orders_digitizing, 'order_digitizing', 'Digitizing order') +
        _collect_uploads(orders_patches,    'order_patches',    'Patches order') +
        _collect_uploads(orders_vector,     'order_vector',     'Vector order') +
        _collect_uploads(quotes_digitizing, 'quote_digitizing', 'Digitizing quote') +
        _collect_uploads(quotes_patches,    'quote_patches',    'Patches quote') +
        _collect_uploads(quotes_vector,     'quote_vector',     'Vector quote')
    )
    all_uploads.sort(key=lambda r: r['uploaded_at'], reverse=True)

    context = {
        'stats': stats,

        # New separate-table querysets for template
        'orders_digitizing': orders_digitizing,
        'orders_patches':    orders_patches,
        'orders_vector':     orders_vector,
        'quotes_digitizing': quotes_digitizing,
        'quotes_patches':    quotes_patches,
        'quotes_vector':     quotes_vector,

        # Finished orders ready for final download (design files + invoice/receipt)
        'downloads_digitizing': downloads_digitizing,
        'downloads_patches':    downloads_patches,
        'downloads_vector':     downloads_vector,

        # All files the client has sent, for the Uploads tab (view-only)
        'all_uploads':     all_uploads,

        # Legacy querysets (for backward compat)
        'orders':            legacy_orders,
        'quotes':            legacy_quotes,
        'invoices_uninvoiced': invoices.filter(status='uninvoiced'),
        'invoices_unpaid':     invoices.filter(status='unpaid'),
        'invoices_paid':       invoices.filter(status='paid'),

        # New per-item billing invoices (mirrors rsd_temp.xlsx template)
        'billing_invoices_unpaid': billing_invoices.filter(status='unpaid'),
        'billing_invoices_paid':   billing_invoices.filter(status='paid'),

        'view': request.GET.get('view', 'dashboard'),

        # Forms – PLACE NEW ORDER
        'order_digitizing_form': OrderDigitizingForm(),
        'order_patches_form':    OrderPatchesForm(),
        'order_vector_form':     OrderVectorForm(),
        # Forms – ADD NEW QUOTE
        'quote_digitizing_form': QuoteDigitizingForm(),
        'quote_patches_form':    QuotePatchesForm(),
        'quote_vector_form':     QuoteVectorForm(),

        'profile_form': ProfileForm(instance=user),
    }
    return render(request, 'dashboard.html', context)


# ─── PLACE NEW ORDER ──────────────────────────────────────────────────────────

@login_required(login_url='/auth/')
def place_order(request):
    if request.method != 'POST':
        return redirect('dashboard')

    order_type = request.POST.get('order_type', 'digitizing')
    FORM_MAP = {
        'digitizing': OrderDigitizingForm,
        'patches':    OrderPatchesForm,
        'vector':     OrderVectorForm,
    }
    FormClass = FORM_MAP.get(order_type, OrderDigitizingForm)

    post_data = request.POST.copy()
    size_unit = post_data.get('size_unit') or post_data.get('height_unit') or post_data.get('width_unit') or 'in'
    post_data['size_unit'] = size_unit
    post_data['urgent'] = 'true' if post_data.get('urgent') == 'on' else 'false'

    form = FormClass(post_data, request.FILES)

    if form.is_valid():
        obj          = form.save(commit=False)
        obj.user     = request.user
        obj.size_unit = size_unit
        obj.urgent   = (post_data.get('urgent') == 'true')
        obj.save()
        _save_extra_files(request, obj, OrderFile)
        messages.success(request, f"✅ {order_type.capitalize()} Order #{obj.pk} placed successfully!")
    else:
        for field, errs in form.errors.items():
            for e in errs:
                messages.error(request, str(e))

    return redirect('/dashboard/?view=orders')


# ─── ADD NEW QUOTE ────────────────────────────────────────────────────────────

@login_required(login_url='/auth/')
def place_quote(request):
    if request.method != 'POST':
        return redirect('dashboard')

    quote_type = request.POST.get('quote_type', 'digitizing')
    FORM_MAP = {
        'digitizing': QuoteDigitizingForm,
        'patches':    QuotePatchesForm,
        'vector':     QuoteVectorForm,
    }
    FormClass = FORM_MAP.get(quote_type, QuoteDigitizingForm)

    post_data = request.POST.copy()
    size_unit = post_data.get('size_unit') or post_data.get('height_unit') or post_data.get('width_unit') or 'in'
    post_data['size_unit'] = size_unit
    post_data['urgent'] = 'true' if post_data.get('urgent') == 'on' else 'false'

    form = FormClass(post_data, request.FILES)

    if form.is_valid():
        obj          = form.save(commit=False)
        obj.user     = request.user
        obj.size_unit = size_unit
        obj.urgent   = (post_data.get('urgent') == 'true')
        obj.save()
        _save_extra_files(request, obj, QuoteFile)
        messages.success(request, f"✅ {quote_type.capitalize()} Quote #{obj.pk} submitted successfully!")
    else:
        for field, errs in form.errors.items():
            for e in errs:
                messages.error(request, str(e))

    return redirect('/dashboard/?view=quotes')


# ─── EDIT EXISTING ORDER ──────────────────────────────────────────────────────

ORDER_MODEL_MAP = {
    'digitizing': (OrderDigitizing, OrderDigitizingForm),
    'patches':    (OrderPatches,    OrderPatchesForm),
    'vector':     (OrderVector,     OrderVectorForm),
}

QUOTE_MODEL_MAP = {
    'digitizing': (QuoteDigitizing, QuoteDigitizingForm),
    'patches':    (QuotePatches,    QuotePatchesForm),
    'vector':     (QuoteVector,     QuoteVectorForm),
}


@login_required(login_url='/auth/')
def edit_order(request, order_type, pk):
    if request.method != 'POST':
        return redirect('/dashboard/?view=orders')

    Model, FormClass = ORDER_MODEL_MAP.get(order_type, (None, None))
    if Model is None:
        messages.error(request, "Unknown order type.")
        return redirect('/dashboard/?view=orders')

    obj = get_object_or_404(Model, pk=pk, user=request.user)

    post_data = request.POST.copy()
    size_unit = post_data.get('size_unit') or post_data.get('height_unit') or post_data.get('width_unit') or obj.size_unit or 'in'
    post_data['size_unit'] = size_unit
    post_data['urgent'] = 'true' if post_data.get('urgent') == 'on' else 'false'

    form = FormClass(post_data, request.FILES, instance=obj)

    if form.is_valid():
        updated           = form.save(commit=False)
        updated.size_unit = size_unit
        updated.urgent    = (post_data.get('urgent') == 'true')
        updated.save()
        _save_extra_files(request, updated, OrderFile)
        messages.success(request, f"✅ {order_type.capitalize()} Order #{updated.pk} updated successfully!")
    else:
        for field, errs in form.errors.items():
            for e in errs:
                messages.error(request, str(e))

    return redirect('/dashboard/?view=orders')


# ─── EDIT EXISTING QUOTE ──────────────────────────────────────────────────────

@login_required(login_url='/auth/')
def edit_quote(request, quote_type, pk):
    if request.method != 'POST':
        return redirect('/dashboard/?view=quotes')

    Model, FormClass = QUOTE_MODEL_MAP.get(quote_type, (None, None))
    if Model is None:
        messages.error(request, "Unknown quote type.")
        return redirect('/dashboard/?view=quotes')

    obj = get_object_or_404(Model, pk=pk, user=request.user)

    post_data = request.POST.copy()
    size_unit = post_data.get('size_unit') or post_data.get('height_unit') or post_data.get('width_unit') or obj.size_unit or 'in'
    post_data['size_unit'] = size_unit
    post_data['urgent'] = 'true' if post_data.get('urgent') == 'on' else 'false'

    form = FormClass(post_data, request.FILES, instance=obj)

    if form.is_valid():
        updated           = form.save(commit=False)
        updated.size_unit = size_unit
        updated.urgent    = (post_data.get('urgent') == 'true')
        updated.save()
        _save_extra_files(request, updated, QuoteFile)
        messages.success(request, f"✅ {quote_type.capitalize()} Quote #{updated.pk} updated successfully!")
    else:
        for field, errs in form.errors.items():
            for e in errs:
                messages.error(request, str(e))

    return redirect('/dashboard/?view=quotes')


# ─── CLIENT: RESPOND TO QUOTATION (Step 3 — accept / reject) ────────────────

@login_required(login_url='/auth/')
def client_quote_action(request, quote_type, pk, action):
    if request.method != 'POST':
        return redirect('/dashboard/?view=quotes')

    Model, _ = QUOTE_MODEL_MAP.get(quote_type, (None, None))
    if Model is None:
        messages.error(request, "Unknown quote type.")
        return redirect('/dashboard/?view=quotes')

    quote = get_object_or_404(Model, pk=pk, user=request.user)

    if not quote.client_can_respond_to_quote:
        messages.error(request, "This quotation can no longer be responded to.")
        return redirect('/dashboard/?view=quotes')

    if action == 'accept':
        quote.status = 'confirmed'
        quote.save()
        OrderModel, _ = ORDER_MODEL_MAP[quote_type]

        # Explicit field copy per type — safer than diffing model _meta, since
        # a couple of field names (description/instructions) differ by design.
        common = dict(
            design_name=quote.design_name, po_number=quote.po_number,
            colors=quote.colors, urgent=quote.urgent, date_needed=quote.date_needed,
            design_file=quote.design_file,
        )
        if quote_type == 'digitizing':
            common.update(
                width_mm=quote.width_mm, height_mm=quote.height_mm, size_unit=quote.size_unit,
                fabric=quote.fabric, placement=quote.placement,
                instructions=quote.description,
            )
        elif quote_type == 'patches':
            common.update(
                width_mm=quote.width_mm, height_mm=quote.height_mm, size_unit=quote.size_unit,
                patch_type=quote.patch_type, backing=quote.backing, quantity=quote.quantity,
                embroidery_pct=quote.embroidery_pct, thread_color=quote.thread_color,
                instructions=quote.description,
            )
        elif quote_type == 'vector':
            common.update(
                vector_format=quote.vector_format, background=quote.background,
                instructions=quote.description,
            )

        new_order = OrderModel.objects.create(
            user=request.user, status='confirmed', price=quote.quoted_price, **common,
        )
        messages.success(request, f"✅ Quote accepted — Order #{new_order.pk} created and confirmed.")
    elif action == 'reject':
        quote.status = 'rejected'
        quote.save()
        messages.success(request, "Quotation rejected.")
    elif action == 'modify':
        comment = request.POST.get('comment', '').strip()
        if comment:
            quote.client_notes = comment
        messages.success(request, "Modification request sent to staff.")
        quote.save()
    else:
        messages.error(request, "Unknown action.")

    return redirect('/dashboard/?view=quotes')


# ─── CLIENT: ORDER REVIEW / CORRECTIONS / PAYMENT (Steps 5–7) ────────────────

def _generate_invoice_for_order(order, order_type, payment_method):
    """Auto-generate a paid BillingInvoice + line item for a just-paid order,
    unless one already exists for it. Relies on _next_invoice_number(), defined
    further down in this module (module-level functions resolve by call time,
    not definition order)."""
    content_type = ContentType.objects.get_for_model(order)
    existing = BillingInvoice.objects.filter(content_type=content_type, object_id=order.pk).first()
    if existing:
        return existing
    invoice = BillingInvoice.objects.create(
        user=order.user,
        invoice_number=_next_invoice_number(),
        invoice_date=timezone.now().date(),
        status='paid',
        payment_method=payment_method,
        bill_to_name=order.user.get_full_name() or order.user.email,
        bill_to_contact=order.user.email,
        content_type=content_type,
        object_id=order.pk,
        paid_at=timezone.now(),
    )
    BillingInvoiceItem.objects.create(
        invoice=invoice,
        description=f"{order.design_name} ({order_type.capitalize()} order)",
        qty=1,
        unit_price=order.price or 0,
    )
    return invoice


@login_required(login_url='/auth/')
def client_order_action(request, order_type, pk, action):
    if request.method != 'POST':
        return redirect('/dashboard/?view=orders')

    Model, _ = ORDER_MODEL_MAP.get(order_type, (None, None))
    if Model is None:
        messages.error(request, "Unknown order type.")
        return redirect('/dashboard/?view=orders')

    order = get_object_or_404(Model, pk=pk, user=request.user)

    if action == 'approve':
        if not order.client_can_request_correction:
            messages.error(request, "This order isn't ready for review yet.")
            return redirect('/dashboard/?view=orders')
        order.status = 'payment_pending'
        order.save()
        messages.success(request, "✅ Design approved — please proceed to payment.")

    elif action == 'request_correction':
        if not order.client_can_request_correction:
            messages.error(request, "This order isn't ready for review yet.")
            return redirect('/dashboard/?view=orders')
        comment = request.POST.get('comment', '').strip()
        if not comment:
            messages.error(request, "Please describe the correction you need.")
            return redirect('/dashboard/?view=orders')
        order.client_notes = comment
        order.status = 'correction_requested'
        order.save()
        messages.success(request, "✅ Correction request sent to staff.")

    elif action == 'pay':
        if not order.client_can_pay:
            messages.error(request, "This order isn't awaiting payment.")
            return redirect('/dashboard/?view=orders')
        method = request.POST.get('payment_method')
        if method not in dict(PAYMENT_METHOD_CHOICES):
            messages.error(request, "Please choose a valid payment method.")
            return redirect('/dashboard/?view=orders')
        # Mock payment confirmation — swap in a real Razorpay/Stripe/PayPal/UPI
        # charge here; on success this same block still runs.
        order.status = 'payment_completed'
        order.save()
        _generate_invoice_for_order(order, order_type, method)
        order.status = 'invoice_generated'
        order.save()
        order.status = 'download_available'
        order.save()
        messages.success(request, "✅ Payment received — invoice generated, download unlocked.")

    else:
        messages.error(request, "Unknown action.")

    return redirect('/dashboard/?view=orders')


@login_required(login_url='/auth/')
def download_final(request, order_type, pk):
    Model, _ = ORDER_MODEL_MAP.get(order_type, (None, None))
    if Model is None:
        return HttpResponseForbidden("Unknown order type.")
    order = get_object_or_404(Model, pk=pk)
    if order.user_id != request.user.id and not request.user.is_staff:
        return HttpResponseForbidden("You don't have access to this file.")
    if not order.is_download_unlocked and not request.user.is_staff:
        messages.info(request, "This design unlocks for download once payment is completed.")
        return redirect('/dashboard/?view=downloads')
    if not order.design_file:
        messages.error(request, "No final file has been uploaded yet.")
        return redirect('/dashboard/?view=downloads')
    return redirect(order.design_file.url)


# ─── PROFILE UPDATE ───────────────────────────────────────────────────────────

@login_required(login_url='/auth/')
def update_profile(request):
    if request.method != 'POST':
        return redirect('dashboard')

    form = ProfileForm(request.POST, instance=request.user)
    if form.is_valid():
        user          = form.save(commit=False)
        user.username = user.email
        user.save()
        messages.success(request, "Profile updated successfully!")
    else:
        for field, errs in form.errors.items():
            for e in errs:
                messages.error(request, str(e))

    return redirect('/dashboard/?view=profile')


# ─── STAFF ADMIN PAGE (custom-styled, not Django /admin/) ────────────────────

# Source models that a billing invoice can be generated from
BILLING_SOURCE_MODELS = {
    'order_digitizing': OrderDigitizing,
    'order_patches':    OrderPatches,
    'order_vector':     OrderVector,
    'quote_digitizing': QuoteDigitizing,
    'quote_patches':    QuotePatches,
    'quote_vector':     QuoteVector,
}


def _next_invoice_number():
    last = BillingInvoice.objects.order_by('-id').first()
    n = (last.id + 1) if last else 1
    return f"RS{n:06d}"


@staff_required
def admin_dashboard(request):
    """Custom-styled staff admin page — separate from Django's /admin/."""
    invoices = BillingInvoice.objects.select_related('user').prefetch_related('items')

    context = {
        'invoices':       invoices,
        'unpaid_count':   invoices.filter(status='unpaid').count(),
        'paid_count':     invoices.filter(status='paid').count(),
        'orders_digitizing': OrderDigitizing.objects.select_related('user')[:100],
        'orders_patches':    OrderPatches.objects.select_related('user')[:100],
        'orders_vector':     OrderVector.objects.select_related('user')[:100],
        'quotes_digitizing': QuoteDigitizing.objects.select_related('user')[:100],
        'quotes_patches':    QuotePatches.objects.select_related('user')[:100],
        'quotes_vector':     QuoteVector.objects.select_related('user')[:100],
        'view': request.GET.get('view', 'invoices'),
    }
    return render(request, 'admin_dashboard.html', context)


STAFF_ORDER_MODEL_MAP = {
    'digitizing': (OrderDigitizing, StaffOrderDigitizingForm),
    'patches':    (OrderPatches,    StaffOrderPatchesForm),
    'vector':     (OrderVector,     StaffOrderVectorForm),
}


@staff_required
def admin_order_edit(request, order_type, pk):
    """Staff order edit page: update an order's status, price, and
    preview/final design file. Its own page (not a modal) so staff can see
    the full order context while editing."""
    Model, FormClass = STAFF_ORDER_MODEL_MAP.get(order_type, (None, None))
    if Model is None:
        messages.error(request, "Unknown order type.")
        return redirect('/staff-admin/?view=orders')

    obj = get_object_or_404(Model, pk=pk)

    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Order #{obj.pk} updated.")
            return redirect('/staff-admin/?view=orders')
        for field, errs in form.errors.items():
            for e in errs:
                messages.error(request, str(e))
    else:
        form = FormClass(instance=obj)

    return render(request, 'admin_order_edit.html', {
        'form': form, 'order': obj, 'order_type': order_type,
    })


STAFF_QUOTE_MODEL_MAP = {
    'digitizing': (QuoteDigitizing, StaffQuoteDigitizingForm),
    'patches':    (QuotePatches,    StaffQuotePatchesForm),
    'vector':     (QuoteVector,     StaffQuoteVectorForm),
}


@staff_required
def admin_quote_edit(request, quote_type, pk):
    """Staff quote edit page: estimate cost, add notes, and send the
    quotation (status -> quote_sent) so the client can accept/reject it."""
    Model, FormClass = STAFF_QUOTE_MODEL_MAP.get(quote_type, (None, None))
    if Model is None:
        messages.error(request, "Unknown quote type.")
        return redirect('/staff-admin/?view=quotes')

    obj = get_object_or_404(Model, pk=pk)

    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Quote #{obj.pk} updated.")
            return redirect('/staff-admin/?view=quotes')
        for field, errs in form.errors.items():
            for e in errs:
                messages.error(request, str(e))
    else:
        form = FormClass(instance=obj)

    return render(request, 'admin_quote_edit.html', {
        'form': form, 'quote': obj, 'quote_type': quote_type,
    })


@staff_required
def admin_invoice_create(request):
    """Create a billing invoice, optionally pre-filled from an order/quote
    (?source=order_digitizing&pk=3)."""
    initial = {'invoice_number': _next_invoice_number()}
    source_key = request.GET.get('source') or request.POST.get('source')
    source_pk  = request.GET.get('pk') or request.POST.get('pk')
    source_obj = None
    source_label = None
    Model = BILLING_SOURCE_MODELS.get(source_key)
    if Model and source_pk:
        source_obj = get_object_or_404(Model, pk=source_pk)
        initial['user'] = source_obj.user_id

    if request.method == 'POST':
        form = BillingInvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            if Model and source_pk:
                invoice.content_type = ContentType.objects.get_for_model(Model)
                invoice.object_id = source_pk
            invoice.save()
            formset = BillingInvoiceItemFormSet(request.POST, instance=invoice)
            if formset.is_valid():
                formset.save()
            else:
                for f in formset:
                    for field, errs in f.errors.items():
                        for e in errs:
                            messages.error(request, str(e))
            messages.success(request, f"✅ Invoice {invoice.invoice_number} created.")
            return redirect('/staff-admin/?view=invoices')
        else:
            for field, errs in form.errors.items():
                for e in errs:
                    messages.error(request, str(e))
            formset = BillingInvoiceItemFormSet(request.POST)
    else:
        line_items_initial = []
        if source_obj is not None:
            price = getattr(source_obj, 'price', None) or getattr(source_obj, 'quoted_price', None)
            source_label = source_obj._meta.verbose_name
            line_items_initial = [{
                'description': f"{source_obj.design_name} ({source_label})",
                'qty': 1,
                'unit_price': price or 0,
            }]
            initial['bill_to_name'] = source_obj.user.get_full_name()
            initial['bill_to_contact'] = source_obj.user.email

        form = BillingInvoiceForm(initial=initial)
        formset = BillingInvoiceItemFormSet(initial=line_items_initial)
        formset.extra = max(formset.extra, len(line_items_initial) + 2)

    return render(request, 'admin_invoice_form.html', {
        'form': form, 'formset': formset, 'source_obj': source_obj,
        'source_label': source_label if source_obj is not None else None,
        'sources': BILLING_SOURCE_MODELS,
    })


@staff_required
def admin_invoice_edit(request, pk):
    invoice = get_object_or_404(BillingInvoice, pk=pk)
    if request.method == 'POST':
        form = BillingInvoiceForm(request.POST, instance=invoice)
        formset = BillingInvoiceItemFormSet(request.POST, instance=invoice)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f"✅ Invoice {invoice.invoice_number} updated.")
            return redirect('/staff-admin/?view=invoices')
        for f_errs in [form.errors] + [f.errors for f in formset]:
            for field, errs in f_errs.items():
                for e in errs:
                    messages.error(request, str(e))
    else:
        form = BillingInvoiceForm(instance=invoice)
        formset = BillingInvoiceItemFormSet(instance=invoice)

    return render(request, 'admin_invoice_form.html', {
        'form': form, 'formset': formset, 'invoice': invoice,
        'sources': BILLING_SOURCE_MODELS,
    })


@staff_required
def admin_invoice_mark_paid(request, pk):
    invoice = get_object_or_404(BillingInvoice, pk=pk)
    if request.method == 'POST':
        from django.utils import timezone
        invoice.status = 'paid'
        invoice.paid_at = timezone.now()
        invoice.save()
        messages.success(request, f"✅ Invoice {invoice.invoice_number} marked paid.")
    return redirect('/staff-admin/?view=invoices')


@login_required(login_url='/auth/')
def invoice_detail(request, pk):
    """Printable invoice, matching the rsd_temp.xlsx layout. Viewable by the
    invoice's owner or by staff."""
    invoice = get_object_or_404(BillingInvoice, pk=pk)
    if invoice.user_id != request.user.id and not request.user.is_staff:
        return HttpResponseForbidden("You don't have access to this invoice.")
    return render(request, 'invoice_detail.html', {'invoice': invoice})


@login_required(login_url='/auth/')
def receipt_detail(request, pk):
    """Printable payment receipt — only available once an invoice has
    actually been paid. Viewable by the invoice's owner or by staff."""
    invoice = get_object_or_404(BillingInvoice, pk=pk)
    if invoice.user_id != request.user.id and not request.user.is_staff:
        return HttpResponseForbidden("You don't have access to this receipt.")
    if invoice.status != 'paid':
        messages.info(request, "A receipt is available once this invoice has been paid.")
        return redirect('invoice_detail', pk=invoice.pk)
    return render(request, 'receipt_detail.html', {'invoice': invoice})
