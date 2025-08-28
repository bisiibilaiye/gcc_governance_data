# GCC Corporate Governance Data Stewardship System - Version 1
## Django-Based Proof of Concept Architecture

---

## **Executive Summary**

This document outlines a Django-based MVP approach for building a scalable data stewardship system. Django's built-in admin interface, robust ORM, and mature ecosystem make it ideal for rapid development of a data governance platform with built-in user management and audit capabilities.

**Why Django?**
- **Built-in Admin Interface** - Ready-made steward dashboard
- **Mature Authentication** - User roles, permissions, groups out of the box
- **Excellent ORM** - Perfect for complex data relationships and history tracking
- **Django REST Framework** - Professional API with auto-documentation
- **Rapid Development** - Get to MVP faster with less custom code

**Core Components:**
1. **Data Extraction Engine** (your existing scraper + Django models)
2. **Django Admin** (steward interface)
3. **Change Detection System** (Django models + signals)
4. **Approval Workflow** (custom admin actions)
5. **Audit Trail** (django-simple-history)
6. **REST API** (Django REST Framework)

---

## **1. SYSTEM ARCHITECTURE OVERVIEW**

### **1.1 Django Project Structure**

```
gcc_stewardship/
├── manage.py
├── requirements.txt
├── gcc_stewardship/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   └── urls.py
├── apps/
│   ├── core/                    # Core models and utilities
│   │   ├── models.py           # Base models
│   │   ├── admin.py            # Admin customizations
│   │   ├── managers.py         # Custom managers
│   │   └── utils.py
│   ├── extractions/            # Data extraction app
│   │   ├── models.py           # Raw data, extraction runs
│   │   ├── tasks.py            # Celery tasks for scraping
│   │   ├── services.py         # Business logic
│   │   └── management/         # Django commands
│   ├── governance/             # Corporate governance data
│   │   ├── models.py           # Companies, board members
│   │   ├── admin.py            # Steward interface
│   │   └── serializers.py      # DRF serializers
│   ├── stewardship/            # Review and approval workflow
│   │   ├── models.py           # Change queue, approvals
│   │   ├── admin.py            # Review interface
│   │   ├── views.py            # Custom admin views
│   │   └── workflows.py        # Approval logic
│   └── api/                    # Public API
│       ├── views.py            # API endpoints
│       ├── serializers.py      # API serializers
│       └── permissions.py      # API access control
└── templates/                  # Custom admin templates
    └── admin/
        ├── base_site.html
        └── stewardship/
```

### **1.2 High-Level Data Flow**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Exchange      │    │   Celery Task    │    │   Raw           │
│   Websites      │───▶│   (Your Scraper) │───▶│   Extractions   │
│                 │    │                  │    │   (Django Model)│
│ • DFM, ADX      │    │ • Rate limiting  │    │                 │
│ • Saudi, etc.   │    │ • Error handling │    │ • JSON data     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Public API    │    │   Django Admin   │    │   Change        │
│   (DRF)         │    │   (Stewards)     │    │   Detection     │
│                 │◀───│                  │◀───│   (Signals)     │
│ • Authentication│    │ • Review queue   │    │                 │
│ • Rate limiting │    │ • Bulk actions   │    │ • Auto-detect   │
│ • Pagination    │    │ • Custom views   │    │ • Priority calc │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Approved      │    │   Audit Trail   │
                       │   Data          │    │   (History)     │
                       │   (Public)      │    │                 │
                       │ • Clean data    │    │ • All changes   │
                       │ • Version ctrl  │    │ • User tracking │
                       │ • API ready     │    │ • Timestamps    │
                       └─────────────────┘    └─────────────────┘
```

---

## **2. DJANGO MODELS DESIGN**

### **2.1 Core Models**

```python
# apps/core/models.py
from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
import uuid

class TimeStampedModel(models.Model):
    """Base model with timestamps"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

class Exchange(models.Model):
    """GCC Stock Exchanges"""
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=50)
    website = models.URLField()
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.code} - {self.name}"

class UserProfile(models.Model):
    """Extended user profile for stewards"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    exchanges = models.ManyToManyField(Exchange, blank=True)
    role = models.CharField(max_length=50, choices=[
        ('STEWARD', 'Data Steward'),
        ('QA_REVIEWER', 'Quality Assurance'),
        ('ADMIN', 'Administrator'),
    ])
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.role}"
```

### **2.2 Extraction Models**

```python
# apps/extractions/models.py
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import TimeStampedModel, Exchange
import uuid
import hashlib
import json

class ExtractionRun(TimeStampedModel):
    """Tracks each scraping run"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=[
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('PARTIAL', 'Partial Success'),
    ], default='RUNNING')
    started_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    companies_found = models.IntegerField(default=0)
    companies_processed = models.IntegerField(default=0)
    changes_detected = models.IntegerField(default=0)
    errors_count = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.exchange.code} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class RawExtraction(TimeStampedModel):
    """Raw scraped data - immutable"""
    extraction_run = models.ForeignKey(ExtractionRun, on_delete=models.CASCADE)
    company_symbol = models.CharField(max_length=50)
    raw_data = models.JSONField()
    data_hash = models.CharField(max_length=64, db_index=True)
    scraper_version = models.CharField(max_length=20)
    
    class Meta:
        indexes = [
            models.Index(fields=['company_symbol', 'extraction_run']),
            models.Index(fields=['data_hash']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.data_hash:
            self.data_hash = hashlib.sha256(
                json.dumps(self.raw_data, sort_keys=True).encode()
            ).hexdigest()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.company_symbol} - {self.extraction_run.exchange.code}"
```

### **2.3 Governance Models**

```python
# apps/governance/models.py
from django.db import models
from apps.core.models import TimeStampedModel, Exchange
from simple_history.models import HistoricalRecords
from django.contrib.auth.models import User

class Company(TimeStampedModel):
    """Approved company data"""
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    name_arabic = models.CharField(max_length=200, blank=True)
    sector = models.CharField(max_length=100, blank=True)
    isin = models.CharField(max_length=50, blank=True)
    listing_date = models.DateField(null=True, blank=True)
    market_segment = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    
    # Detailed information
    incorporation_date = models.DateField(null=True, blank=True)
    share_capital = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    company_type = models.CharField(max_length=100, blank=True)
    auditor = models.CharField(max_length=200, blank=True)
    fiscal_year_end = models.CharField(max_length=20, blank=True)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    last_verified = models.DateTimeField(auto_now=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Audit trail
    history = HistoricalRecords()
    
    class Meta:
        unique_together = ['exchange', 'symbol']
        ordering = ['exchange', 'symbol']
    
    def __str__(self):
        return f"{self.exchange.code}:{self.symbol} - {self.name}"

class BoardMember(TimeStampedModel):
    """Board member information"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='board_members')
    name = models.CharField(max_length=200)
    name_arabic = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=100)
    designation = models.CharField(max_length=100, blank=True)
    member_type = models.CharField(max_length=50, choices=[
        ('EXECUTIVE', 'Executive'),
        ('NON_EXECUTIVE', 'Non-Executive'),
        ('INDEPENDENT', 'Independent'),
        ('REPRESENTATIVE', 'Representative'),
    ], blank=True)
    
    # Additional details
    nationality = models.CharField(max_length=50, blank=True)
    qualifications = models.TextField(blank=True)
    experience = models.TextField(blank=True)
    other_positions = models.TextField(blank=True)
    appointment_date = models.DateField(null=True, blank=True)
    
    # Metadata
    is_current = models.BooleanField(default=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Audit trail
    history = HistoricalRecords()
    
    class Meta:
        ordering = ['company', 'position', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.position} at {self.company.symbol}"
```

### **2.4 Stewardship Models**

```python
# apps/stewardship/models.py
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import TimeStampedModel, Exchange
from apps.governance.models import Company

class ChangeQueue(TimeStampedModel):
    """Queue for changes requiring steward review"""
    
    CHANGE_TYPES = [
        ('NEW_COMPANY', 'New Company'),
        ('COMPANY_UPDATE', 'Company Update'),
        ('NEW_BOARD_MEMBER', 'New Board Member'),
        ('BOARD_MEMBER_UPDATE', 'Board Member Update'),
        ('BOARD_MEMBER_DEPARTURE', 'Board Member Departure'),
    ]
    
    STATUSES = [
        ('PENDING', 'Pending Review'),
        ('IN_REVIEW', 'In Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('NEEDS_INFO', 'Needs More Information'),
    ]
    
    PRIORITIES = [
        (1, 'Critical'),
        (2, 'High'),
        (3, 'Medium'),
        (4, 'Low'),
    ]
    
    # Basic info
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE)
    company_symbol = models.CharField(max_length=50)
    change_type = models.CharField(max_length=30, choices=CHANGE_TYPES)
    priority = models.IntegerField(choices=PRIORITIES, default=3)
    
    # Data
    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField()
    change_summary = models.TextField()
    
    # Workflow
    status = models.CharField(max_length=20, choices=STATUSES, default='PENDING')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_changes')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Notes and reasoning
    steward_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['priority', 'created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['exchange', 'status']),
            models.Index(fields=['assigned_to', 'status']),
        ]
    
    def __str__(self):
        return f"{self.exchange.code}:{self.company_symbol} - {self.change_type} ({self.status})"

class ApprovalAction(TimeStampedModel):
    """Track approval actions for audit"""
    change = models.ForeignKey(ChangeQueue, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=[
        ('APPROVE', 'Approved'),
        ('REJECT', 'Rejected'),
        ('REQUEST_INFO', 'Requested More Info'),
        ('EDIT_APPROVE', 'Edited and Approved'),
    ])
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.TextField()
    data_changes = models.JSONField(null=True, blank=True)  # If data was edited
    
    def __str__(self):
        return f"{self.action} by {self.user.username} - {self.change}"
```

---

## **3. DJANGO ADMIN INTERFACE**

### **3.1 Steward Dashboard (Django Admin)**

```python
# apps/stewardship/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.utils import timezone
import json

from .models import ChangeQueue, ApprovalAction
from .workflows import ApprovalWorkflow

@admin.register(ChangeQueue)
class ChangeQueueAdmin(admin.ModelAdmin):
    list_display = ['company_info', 'change_type', 'priority_badge', 'status_badge', 'created_at', 'assigned_to']
    list_filter = ['status', 'priority', 'exchange', 'change_type', 'created_at']
    search_fields = ['company_symbol', 'change_summary']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Change Information', {
            'fields': ['exchange', 'company_symbol', 'change_type', 'priority', 'change_summary']
        }),
        ('Data', {
            'fields': ['old_data_display', 'new_data_display'],
            'classes': ['collapse']
        }),
        ('Workflow', {
            'fields': ['status', 'assigned_to', 'steward_notes']
        }),
        ('Review Information', {
            'fields': ['reviewed_by', 'reviewed_at', 'rejection_reason'],
            'classes': ['collapse']
        }),
    )
    
    def company_info(self, obj):
        return f"{obj.exchange.code}:{obj.company_symbol}"
    company_info.short_description = "Company"
    
    def priority_badge(self, obj):
        colors = {1: 'red', 2: 'orange', 3: 'blue', 4: 'green'}
        labels = {1: 'Critical', 2: 'High', 3: 'Medium', 4: 'Low'}
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.priority, 'black'),
            labels.get(obj.priority, obj.priority)
        )
    priority_badge.short_description = "Priority"
    
    def status_badge(self, obj):
        colors = {
            'PENDING': 'orange',
            'IN_REVIEW': 'blue',
            'APPROVED': 'green',
            'REJECTED': 'red',
            'NEEDS_INFO': 'purple'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_badge.short_description = "Status"
    
    def old_data_display(self, obj):
        if obj.old_data:
            return format_html('<pre>{}</pre>', json.dumps(obj.old_data, indent=2))
        return "No previous data (new record)"
    old_data_display.short_description = "Previous Data"
    
    def new_data_display(self, obj):
        return format_html('<pre>{}</pre>', json.dumps(obj.new_data, indent=2))
    new_data_display.short_description = "New Data"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Stewards only see their assigned exchanges
        if hasattr(request.user, 'userprofile'):
            profile = request.user.userprofile
            if profile.role == 'STEWARD':
                return qs.filter(exchange__in=profile.exchanges.all())
        return qs
    
    actions = ['approve_selected', 'reject_selected', 'assign_to_me']
    
    def approve_selected(self, request, queryset):
        workflow = ApprovalWorkflow()
        approved_count = 0
        
        for change in queryset.filter(status='PENDING'):
            try:
                workflow.approve_change(change, request.user, "Bulk approval")
                approved_count += 1
            except Exception as e:
                messages.error(request, f"Failed to approve {change}: {str(e)}")
        
        messages.success(request, f"Successfully approved {approved_count} changes")
    approve_selected.short_description = "Approve selected changes"
    
    def reject_selected(self, request, queryset):
        # This would redirect to a form for rejection reasons
        selected = queryset.values_list('id', flat=True)
        return HttpResponseRedirect(
            reverse('admin:stewardship_bulk_reject') + f"?ids={','.join(map(str, selected))}"
        )
    reject_selected.short_description = "Reject selected changes"
    
    def assign_to_me(self, request, queryset):
        updated = queryset.filter(assigned_to__isnull=True).update(
            assigned_to=request.user,
            status='IN_REVIEW'
        )
        messages.success(request, f"Assigned {updated} changes to yourself")
    assign_to_me.short_description = "Assign to me"

# Custom admin views for detailed review
from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def detailed_review(request, change_id):
    """Detailed review page with side-by-side comparison"""
    change = get_object_or_404(ChangeQueue, id=change_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        reason = request.POST.get('reason', '')
        
        workflow = ApprovalWorkflow()
        
        if action == 'approve':
            workflow.approve_change(change, request.user, reason)
            messages.success(request, "Change approved successfully")
        elif action == 'reject':
            workflow.reject_change(change, request.user, reason)
            messages.success(request, "Change rejected")
        
        return HttpResponseRedirect(reverse('admin:stewardship_changequeue_changelist'))
    
    context = {
        'change': change,
        'old_data_formatted': json.dumps(change.old_data, indent=2) if change.old_data else None,
        'new_data_formatted': json.dumps(change.new_data, indent=2),
    }
    
    return render(request, 'admin/stewardship/detailed_review.html', context)
```

### **3.2 Company and Board Member Admin**

```python
# apps/governance/admin.py
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import Company, BoardMember

@admin.register(Company)
class CompanyAdmin(SimpleHistoryAdmin):
    list_display = ['symbol', 'name', 'exchange', 'sector', 'last_verified', 'verified_by']
    list_filter = ['exchange', 'sector', 'is_active', 'last_verified']
    search_fields = ['symbol', 'name', 'name_arabic']
    readonly_fields = ['last_verified']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ['exchange', 'symbol', 'name', 'name_arabic', 'sector']
        }),
        ('Trading Information', {
            'fields': ['isin', 'listing_date', 'market_segment']
        }),
        ('Company Details', {
            'fields': ['incorporation_date', 'share_capital', 'company_type', 'auditor', 'fiscal_year_end'],
            'classes': ['collapse']
        }),
        ('Verification', {
            'fields': ['is_active', 'verified_by', 'last_verified']
        })
    )
    
    def save_model(self, request, obj, form, change):
        obj.verified_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(BoardMember)
class BoardMemberAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'position', 'company', 'member_type', 'is_current']
    list_filter = ['member_type', 'is_current', 'company__exchange']
    search_fields = ['name', 'name_arabic', 'position', 'company__name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ['company', 'name', 'name_arabic', 'position', 'designation']
        }),
        ('Board Role', {
            'fields': ['member_type', 'appointment_date', 'is_current']
        }),
        ('Personal Details', {
            'fields': ['nationality', 'qualifications', 'experience', 'other_positions'],
            'classes': ['collapse']
        }),
        ('Verification', {
            'fields': ['verified_by']
        })
    )
    
    def save_model(self, request, obj, form, change):
        obj.verified_by = request.user
        super().save_model(request, obj, form, change)
```

---

## **4. WORKFLOW INTEGRATION**

### **4.1 Change Detection System**

```python
# apps/stewardship/workflows.py
from django.db import transaction
from django.utils import timezone
from typing import Dict, Any, List
import json

from apps.governance.models import Company, BoardMember
from .models import ChangeQueue, ApprovalAction

class ChangeDetectionService:
    """Detect changes and create review queue items"""
    
    def process_extraction_data(self, extraction_run, raw_extractions):
        """Process raw extractions and detect changes"""
        changes_created = 0
        
        for raw_extraction in raw_extractions:
            symbol = raw_extraction.company_symbol
            exchange = extraction_run.exchange
            new_data = raw_extraction.raw_data
            
            # Check if company exists in approved data
            try:
                existing_company = Company.objects.get(
                    exchange=exchange,
                    symbol=symbol
                )
                changes_created += self._detect_company_changes(
                    existing_company, new_data, raw_extraction
                )
            except Company.DoesNotExist:
                # New company
                self._create_new_company_change(
                    exchange, symbol, new_data, raw_extraction
                )
                changes_created += 1
        
        return changes_created
    
    def _detect_company_changes(self, existing_company, new_data, raw_extraction):
        """Detect changes for existing company"""
        changes_created = 0
        
        # Compare company basic info
        company_data = new_data.get('company', {})
        old_company_data = self._company_to_dict(existing_company)
        
        if self._has_significant_changes(old_company_data, company_data):
            ChangeQueue.objects.create(
                exchange=existing_company.exchange,
                company_symbol=existing_company.symbol,
                change_type='COMPANY_UPDATE',
                old_data={'company': old_company_data},
                new_data={'company': company_data},
                change_summary=self._generate_company_change_summary(old_company_data, company_data),
                priority=self._calculate_company_priority(old_company_data, company_data)
            )
            changes_created += 1
        
        # Compare board members
        new_board_members = new_data.get('board_members', [])
        existing_board_members = list(existing_company.board_members.filter(is_current=True))
        
        board_changes = self._detect_board_changes(
            existing_board_members, new_board_members, existing_company
        )
        changes_created += len(board_changes)
        
        return changes_created
    
    def _detect_board_changes(self, existing_members, new_members, company):
        """Detect board member changes"""
        changes = []
        
        # Create lookup for existing members
        existing_lookup = {
            self._normalize_name(member.name): member 
            for member in existing_members
        }
        
        new_lookup = {
            self._normalize_name(member.get('name', '')): member
            for member in new_members
        }
        
        # Find new members
        for name, member_data in new_lookup.items():
            if name not in existing_lookup:
                change = ChangeQueue.objects.create(
                    exchange=company.exchange,
                    company_symbol=company.symbol,
                    change_type='NEW_BOARD_MEMBER',
                    new_data={'board_member': member_data},
                    change_summary=f"New board member: {member_data.get('name')} as {member_data.get('position')}",
                    priority=2  # High priority for board changes
                )
                changes.append(change)
        
        # Find departures
        for name, existing_member in existing_lookup.items():
            if name not in new_lookup:
                change = ChangeQueue.objects.create(
                    exchange=company.exchange,
                    company_symbol=company.symbol,
                    change_type='BOARD_MEMBER_DEPARTURE',
                    old_data={'board_member': self._board_member_to_dict(existing_member)},
                    new_data={},
                    change_summary=f"Board member departure: {existing_member.name}",
                    priority=2
                )
                changes.append(change)
        
        # Find updates
        for name in set(existing_lookup.keys()) & set(new_lookup.keys()):
            existing_data = self._board_member_to_dict(existing_lookup[name])
            new_data = new_lookup[name]
            
            if self._has_significant_changes(existing_data, new_data):
                change = ChangeQueue.objects.create(
                    exchange=company.exchange,
                    company_symbol=company.symbol,
                    change_type='BOARD_MEMBER_UPDATE',
                    old_data={'board_member': existing_data},
                    new_data={'board_member': new_data},
                    change_summary=f"Board member update: {existing_lookup[name].name}",
                    priority=3
                )
                changes.append(change)
        
        return changes
    
    def _normalize_name(self, name: str) -> str:
        """Normalize names for comparison"""
        return name.strip().lower().replace('.', '').replace(',', '')
    
    def _has_significant_changes(self, old_data: Dict, new_data: Dict) -> bool:
        """Determine if changes are significant enough to require review"""
        # Skip timestamp and metadata fields
        skip_fields = ['created_at', 'updated_at', 'last_verified', 'verified_by']
        
        for key in new_data:
            if key in skip_fields:
                continue
            if old_data.get(key) != new_data.get(key):
                return True
        return False

class ApprovalWorkflow:
    """Handle approval workflow"""
    
    @transaction.atomic
    def approve_change(self, change: ChangeQueue, approver, reason: str):
        """Approve a change and update company data"""
        
        if change.change_type == 'NEW_COMPANY':
            self._create_new_company(change)
        elif change.change_type == 'COMPANY_UPDATE':
            self._update_company(change)
        elif change.change_type == 'NEW_BOARD_MEMBER':
            self._create_board_member(change)
        elif change.change_type == 'BOARD_MEMBER_UPDATE':
            self._update_board_member(change)
        elif change.change_type == 'BOARD_MEMBER_DEPARTURE':
            self._handle_board_departure(change)
        
        # Update change record
        change.status = 'APPROVED'
        change.reviewed_by = approver
        change.reviewed_at = timezone.now()
        change.save()
        
        # Log approval action
        ApprovalAction.objects.create(
            change=change,
            action='APPROVE',
            user=approver,
            reason=reason
        )
    
    def reject_change(self, change: ChangeQueue, rejector, reason: str):
        """Reject a change"""
        change.status = 'REJECTED'
        change.reviewed_by = rejector
        change.reviewed_at = timezone.now()
        change.rejection_reason = reason
        change.save()
        
        ApprovalAction.objects.create(
            change=change,
            action='REJECT',
            user=rejector,
            reason=reason
        )
    
    def _create_new_company(self, change):
        """Create new company from approved change"""
        company_data = change.new_data.get('company', {})
        
        company = Company.objects.create(
            exchange=change.exchange,
            symbol=change.company_symbol,
            name=company_data.get('name', ''),
            name_arabic=company_data.get('name_arabic', ''),
            sector=company_data.get('sector', ''),
            isin=company_data.get('isin', ''),
            verified_by=change.reviewed_by
        )
        
        # Create board members if included
        board_members_data = change.new_data.get('board_members', [])
        for member_data in board_members_data:
            BoardMember.objects.create(
                company=company,
                name=member_data.get('name', ''),
                position=member_data.get('position', ''),
                member_type=member_data.get('member_type', ''),
                verified_by=change.reviewed_by
            )
```

### **4.2 Integration with Existing Scraper**

```python
# apps/extractions/tasks.py
from celery import shared_task
from django.utils import timezone
from .models import ExtractionRun, RawExtraction
from apps.stewardship.workflows import ChangeDetectionService

# Import your existing scraper
from scraper import GCCScraperApp  # Your existing scraper

@shared_task
def run_extraction(exchange_code, max_companies=None, user_id=None):
    """Celery task to run extraction"""
    
    from django.contrib.auth.models import User
    from apps.core.models import Exchange
    
    try:
        exchange = Exchange.objects.get(code=exchange_code.upper())
        user = User.objects.get(id=user_id) if user_id else None
        
        # Create extraction run record
        extraction_run = ExtractionRun.objects.create(
            exchange=exchange,
            started_by=user,
            status='RUNNING'
        )
        
        # Run your existing scraper
        scraper_app = GCCScraperApp(verbose=True)
        result = await scraper_app.scrape_exchange(exchange_code.lower(), max_companies)
        
        if result:
            # Process results and save to database
            raw_extractions = []
            
            # You'll need to adapt this to your scraper's output format
            for company_data in result.get('companies', []):
                raw_extraction = RawExtraction(
                    extraction_run=extraction_run,
                    company_symbol=company_data.get('symbol'),
                    raw_data=company_data,
                    scraper_version="1.0"
                )
                raw_extractions.append(raw_extraction)
            
            # Bulk create raw extractions
            RawExtraction.objects.bulk_create(raw_extractions)
            
            # Detect changes
            change_service = ChangeDetectionService()
            changes_detected = change_service.process_extraction_data(
                extraction_run, raw_extractions
            )
            
            # Update extraction run
            extraction_run.status = 'COMPLETED'
            extraction_run.companies_found = len(raw_extractions)
            extraction_run.companies_processed = len(raw_extractions)
            extraction_run.changes_detected = changes_detected
            extraction_run.save()
            
            return f"Extraction completed: {len(raw_extractions)} companies, {changes_detected} changes detected"
        
        else:
            extraction_run.status = 'FAILED'
            extraction_run.save()
            return "Extraction failed"
            
    except Exception as e:
        if 'extraction_run' in locals():
            extraction_run.status = 'FAILED'
            extraction_run.notes = str(e)
            extraction_run.save()
        raise e

# Management command to run extraction
# apps/extractions/management/commands/run_extraction.py
from django.core.management.base import BaseCommand
from apps.extractions.tasks import run_extraction

class Command(BaseCommand):
    help = 'Run data extraction for specified exchange'
    
    def add_arguments(self, parser):
        parser.add_argument('exchange', type=str, help='Exchange code (dfm, adx, saudi, etc.)')
        parser.add_argument('--limit', type=int, help='Limit number of companies')
    
    def handle(self, *args, **options):
        exchange = options['exchange']
        limit = options.get('limit')
        
        self.stdout.write(f'Starting extraction for {exchange}...')
        
        # Run synchronously in management command
        result = run_extraction.apply(args=[exchange, limit])
        
        self.stdout.write(
            self.style.SUCCESS(f'Extraction completed: {result}')
        )
```

---

## **5. REST API IMPLEMENTATION**

### **5.1 Django REST Framework Setup**

```python
# apps/api/serializers.py
from rest_framework import serializers
from apps.governance.models import Company, BoardMember
from apps.core.models import Exchange

class ExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exchange
        fields = ['code', 'name', 'country']

class BoardMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = BoardMember
        fields = [
            'name', 'name_arabic', 'position', 'designation', 
            'member_type', 'nationality', 'appointment_date', 'is_current'
        ]

class CompanySerializer(serializers.ModelSerializer):
    exchange = ExchangeSerializer(read_only=True)
    board_members = BoardMemberSerializer(many=True, read_only=True)
    
    class Meta:
        model = Company
        fields = [
            'symbol', 'name', 'name_arabic', 'sector', 'isin', 
            'listing_date', 'market_segment', 'exchange', 'board_members'
        ]

class CompanyListSerializer(serializers.ModelSerializer):
    exchange = ExchangeSerializer(read_only=True)
    board_members_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Company
        fields = [
            'symbol', 'name', 'sector', 'exchange', 'board_members_count'
        ]
    
    def get_board_members_count(self, obj):
        return obj.board_members.filter(is_current=True).count()
```

### **5.2 API Views**

```python
# apps/api/views.py
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

from apps.governance.models import Company, BoardMember
from apps.core.models import Exchange
from .serializers import CompanySerializer, CompanyListSerializer, BoardMemberSerializer
from .permissions import APIKeyPermission

class CompanyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API for accessing approved company data
    """
    queryset = Company.objects.filter(is_active=True).select_related('exchange').prefetch_related('board_members')
    permission_classes = [APIKeyPermission]
    throttle_classes = [UserRateThrottle, AnonRateThrottle]
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['exchange__code', 'sector']
    search_fields = ['name', 'symbol', 'name_arabic']
    ordering_fields = ['symbol', 'name', 'listing_date']
    ordering = ['exchange__code', 'symbol']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CompanyListSerializer
        return CompanySerializer
    
    @action(detail=True, methods=['get'])
    def board_members(self, request, pk=None):
        """Get board members for a specific company"""
        company = self.get_object()
        board_members = company.board_members.filter(is_current=True)
        serializer = BoardMemberSerializer(board_members, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_exchange(self, request):
        """Group companies by exchange"""
        exchanges = Exchange.objects.filter(is_active=True)
        result = {}
        
        for exchange in exchanges:
            companies = self.queryset.filter(exchange=exchange)
            result[exchange.code] = {
                'exchange': exchange.name,
                'country': exchange.country,
                'companies_count': companies.count(),
                'companies': CompanyListSerializer(companies, many=True).data
            }
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get overall statistics"""
        stats = {}
        
        for exchange in Exchange.objects.filter(is_active=True):
            companies = self.queryset.filter(exchange=exchange)
            stats[exchange.code] = {
                'companies_count': companies.count(),
                'board_members_count': BoardMember.objects.filter(
                    company__exchange=exchange, 
                    is_current=True
                ).count(),
                'sectors': list(companies.values_list('sector', flat=True).distinct())
            }
        
        return Response(stats)

# apps/api/permissions.py
from rest_framework import permissions
from django.conf import settings

class APIKeyPermission(permissions.BasePermission):
    """
    Simple API key authentication
    """
    def has_permission(self, request, view):
        api_key = request.META.get('HTTP_X_API_KEY') or request.GET.get('api_key')
        return api_key == settings.API_KEY

# apps/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CompanyViewSet

router = DefaultRouter()
router.register(r'companies', CompanyViewSet)

urlpatterns = [
    path('v1/', include(router.urls)),
    path('auth/', include('rest_framework.urls')),  # Browsable API login
]
```

---

## **6. SETTINGS CONFIGURATION**

### **6.1 Django Settings**

```python
# gcc_stewardship/settings/base.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Django Apps
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'django_filters',
    'simple_history',
    'corsheaders',
    'django_extensions',
]

LOCAL_APPS = [
    'apps.core',
    'apps.extractions',
    'apps.governance',
    'apps.stewardship',
    'apps.api',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gcc_stewardship.urls'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'gcc_governance'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day'
    }
}

# Celery Configuration
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# API Configuration
API_KEY = os.environ.get('API_KEY', 'your-secret-api-key-here')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'django.log',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
```

---

## **7. DEPLOYMENT & SCALING**

### **7.1 Docker Setup**

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "gcc_stewardship.wsgi:application", "--bind", "0.0.0.0:8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: gcc_governance
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - DEBUG=True
      - DB_HOST=db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  celery:
    build: .
    command: celery -A gcc_stewardship worker --loglevel=info
    volumes:
      - .:/app
    environment:
      - DB_HOST=db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

volumes:
  postgres_data:
```

### **7.2 Quick Start Commands**

```bash
# Initial setup
git clone <your-repo>
cd gcc_stewardship
cp .env.example .env  # Create and configure environment variables

# Development setup
docker-compose up -d db redis
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Database setup
python manage.py migrate
python manage.py createsuperuser

# Create test data
python manage.py loaddata fixtures/initial_exchanges.json

# Run development server
python manage.py runserver

# Run extraction
python manage.py run_extraction dfm --limit 5

# Access interfaces
# Admin: http://localhost:8000/admin/
# API: http://localhost:8000/api/v1/companies/
```

---

## **8. SCALING ROADMAP**

### **8.1 Phase 1: MVP (Current)**
✅ Django admin for stewards  
✅ Basic change detection  
✅ Manual approval workflow  
✅ REST API with authentication  
✅ Audit trail with django-simple-history  

### **8.2 Phase 2: Enhanced UI**
- Custom React frontend for stewards
- Real-time notifications with Django Channels
- Advanced search and filtering
- Bulk operations interface

### **8.3 Phase 3: Automation**
- ML-based change prioritization
- Automated approval for low-risk changes
- Smart data validation rules
- Performance monitoring dashboard

### **8.4 Phase 4: Scale**
- Multi-tenancy support
- Advanced API features (GraphQL)
- Mobile app for stewards
- Integration webhooks

**Success Metrics:**
- Process 600+ companies across 6 exchanges
- <24 hour average review time
- 99%+ data accuracy after steward review
- 50+ API requests/minute sustained
- 3+ concurrent stewards working efficiently

This Django-based approach gives you a solid, scalable foundation with built-in admin interface, robust data models, and clear scaling pathways!

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"id": "7", "content": "Create Django-based proof-of-concept architecture (Version 1)", "status": "completed"}]