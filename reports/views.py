import os
import io
import json
import pandas as pd
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from PIL import Image as PILImage
from .models import MembershipUpload, ComparisonReport, Member

def format_date(date_str):
    """Format date string to show only the date part"""
    try:
        if pd.isna(date_str) or date_str == '0000-00-00 00:00:00':
            return ''
        if isinstance(date_str, str) and not is_valid_date(date_str):
            return date_str  # Return as is if it's a status like 'FREE', 'LINKED', etc.
        date = pd.to_datetime(date_str)
        return date.strftime('%Y-%m-%d')
    except:
        return str(date_str)

def can_upload(user):
    """Check if user has upload permissions"""
    return user.is_superuser or user.groups.filter(name='upload_access').exists()

class UploadPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        return can_upload(self.request.user)
    
    def handle_no_permission(self):
        return redirect('current_members')

def format_phone_number(number):
    """Format phone number to ensure it starts with +"""
    if pd.isna(number):
        return ""
    number = str(number).strip()
    if not number:
        return ""
    if not number.startswith('+'):
        return f'+{number}'
    return number

@login_required
def download_contact(request, cell):
    """Generate and serve a vCard file for the member"""
    latest_upload = MembershipUpload.objects.order_by('-upload_date').first()
    if not latest_upload:
        return HttpResponse('No member data available', status=404)
        
    # Read the CSV data
    df = process_csv_file(latest_upload.file_content, 
                         latest_upload.month, 
                         latest_upload.year)
    
    # Find the member
    member = df[df['cell'].astype(str).str.strip() == str(cell)]
    if len(member) == 0:
        return HttpResponse('Member not found', status=404)
    
    member = member.iloc[0]
    
    # Create vCard content
    vcard = [
        'BEGIN:VCARD',
        'VERSION:3.0',
        f'FN:{member["name"]} {member["surname"]}',
        f'N:{member["surname"]};{member["name"]};;;',
        f'TEL;TYPE=CELL:{format_phone_number(member["cell"])}',
    ]
    
    # Add email if available
    if pd.notna(member.get('email')):
        vcard.append(f'EMAIL:{member["email"]}')
    
    # Add address if available
    address_parts = []
    if pd.notna(member.get('Complex/Building')):
        address_parts.append(member['Complex/Building'])
    if pd.notna(member.get('Street Number')):
        address_parts.append(str(member['Street Number']))
    if pd.notna(member.get('Street')):
        address_parts.append(member['Street'])
    if pd.notna(member.get('Suburb')):
        address_parts.append(member['Suburb'])
    
    if address_parts:
        vcard.append(f'ADR:;;{";".join(address_parts)};;;;')
    
    vcard.append('END:VCARD')
    
    # Create the response
    response = HttpResponse(content_type='text/vcard')
    
    # Check if request is from a mobile device
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = any(device in user_agent for device in ['mobile', 'android', 'iphone', 'ipad', 'webos'])
    
    # Set Content-Disposition based on device type
    if is_mobile:
        response['Content-Disposition'] = f'inline; filename="{member["name"]}_{member["surname"]}.vcf"'
    else:
        response['Content-Disposition'] = f'attachment; filename="{member["name"]}_{member["surname"]}.vcf"'
    
    response.write('\n'.join(vcard))
    return response

def is_valid_date(date_str):
    """Check if a string represents a valid date"""
    try:
        if date_str == '0000-00-00 00:00:00' or pd.isna(date_str):
            return False
        pd.to_datetime(date_str)
        return True
    except:
        return False

def get_member_status(mandate_signed):
    """Determine member status from mandate_signed value"""
    if pd.isna(mandate_signed) or mandate_signed == 'nan':
        return 'LEAD'
    mandate_signed = str(mandate_signed).strip()
    if mandate_signed == '0000-00-00 00:00:00':
        return 'LEAD'
    elif mandate_signed == 'FREE':
        return 'FREE'
    elif mandate_signed == 'LINKED':
        return 'LINKED'
    elif mandate_signed == 'CNCLD':
        return 'CANCELLED'
    elif is_valid_date(mandate_signed):
        return 'ACTIVE'
    else:
        return 'UNKNOWN'

def clean_for_json(value):
    """Clean values to ensure they're JSON serializable"""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)

def process_csv_file(file_obj, month, year):
    """Process uploaded CSV file and return DataFrame"""
    try:
        # Handle different input types
        if isinstance(file_obj, (bytes, memoryview)):
            # Convert bytes or memoryview to string
            file_content = file_obj.tobytes() if isinstance(file_obj, memoryview) else file_obj
            file_obj = io.StringIO(file_content.decode('utf-8'))
            
        df = pd.read_csv(file_obj)
        print(f"Successfully read CSV file. Columns found: {df.columns.tolist()}")
        
        # Clean column names
        df.columns = df.columns.str.strip().str.replace('"', '')
        
        # Rename columns
        column_mapping = {
            'Name': 'name',
            'Surname': 'surname',
            'Cell': 'cell',
            'Email': 'email',
            'Date Mandate Signed': 'mandate_signed'
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                df = df.rename(columns={old_col: new_col})
        
        # Add status column
        df['status'] = df['mandate_signed'].apply(get_member_status)
        
        # Format phone numbers
        df['cell'] = df['cell'].apply(format_phone_number)
        
        # Print sample of statuses
        print("\nSample of records with statuses:")
        sample_df = df.head()
        for _, row in sample_df.iterrows():
            print(f"{row['name']} {row['surname']}: {row['mandate_signed']} -> {row['status']}")
        
        return df
        
    except Exception as e:
        print(f"Error in process_csv_file: {str(e)}")
        raise

def compare_memberships(current_df, previous_df):
    """Compare two membership DataFrames and return changes"""
    try:
        print("Starting comparison...")
        print(f"Current DataFrame shape: {current_df.shape}")
        print(f"Previous DataFrame shape: {previous_df.shape}")
        
        # Convert cell numbers to string and remove any spaces
        current_df['cell'] = current_df['cell'].astype(str).str.strip()
        previous_df['cell'] = previous_df['cell'].astype(str).str.strip()
        
        # Find new members
        new_members = current_df[~current_df['cell'].isin(previous_df['cell'])]
        print(f"Total new members found: {len(new_members)}")
        
        # Function to convert DataFrame records to JSON-safe dictionaries
        def to_json_safe_records(df):
            records = []
            for _, row in df.iterrows():
                record = {}
                for column in ['name', 'surname', 'cell', 'email', 'mandate_signed', 'status']:
                    if column in row:
                        value = row[column]
                        if column == 'mandate_signed':
                            value = format_date(value)
                        record[column] = clean_for_json(value)
                records.append(record)
            return records
        
        # Categorize new members
        new_active = new_members[new_members['status'] == 'ACTIVE']
        new_free = new_members[new_members['status'] == 'FREE']
        new_linked = new_members[new_members['status'] == 'LINKED']
        new_leads = new_members[new_members['status'] == 'LEAD']
        
        print(f"New active members: {len(new_active)}")
        if len(new_active) > 0:
            print("Sample of new active members:")
            print(new_active[['name', 'surname', 'mandate_signed', 'status']].head())
            
        print(f"New free members: {len(new_free)}")
        print(f"New linked members: {len(new_linked)}")
        print(f"New leads: {len(new_leads)}")
        
        # Convert to JSON-safe records
        new_active_records = to_json_safe_records(new_active)
        new_free_records = to_json_safe_records(new_free)
        new_linked_records = to_json_safe_records(new_linked)
        new_leads_records = to_json_safe_records(new_leads)
        
        # Find removed members
        removed_members = previous_df[~previous_df['cell'].isin(current_df['cell'])]
        removed_records = to_json_safe_records(removed_members)
        print(f"Removed members: {len(removed_members)}")
        
        # Find status changes
        status_changes = []
        cancelled_members = []
        common_cells = set(current_df['cell']).intersection(set(previous_df['cell']))
        
        for cell in common_cells:
            current_member = current_df[current_df['cell'] == cell].iloc[0]
            previous_member = previous_df[previous_df['cell'] == cell].iloc[0]
            
            if current_member['mandate_signed'] != previous_member['mandate_signed']:
                change = {
                    'name': clean_for_json(current_member['name']),
                    'surname': clean_for_json(current_member['surname']),
                    'cell': clean_for_json(cell),
                    'old_status': clean_for_json(previous_member['mandate_signed']),
                    'new_status': clean_for_json(current_member['mandate_signed'])
                }
                
                # Check if this is a cancellation
                if current_member['status'] == 'CANCELLED':
                    cancelled_members.append(change)
                else:
                    status_changes.append(change)
        
        print(f"Status changes: {len(status_changes)}")
        print(f"Cancelled members: {len(cancelled_members)}")
        
        changes = {
            'new_active': new_active_records,
            'new_free': new_free_records,
            'new_linked': new_linked_records,
            'new_leads': new_leads_records,
            'removed_members': removed_records,
            'status_changes': status_changes,
            'cancelled_members': cancelled_members
        }
        
        return changes
        
    except Exception as e:
        print(f"Error in compare_memberships: {str(e)}")
        raise

class UploadView(LoginRequiredMixin, UploadPermissionMixin, TemplateView):
    template_name = 'reports/upload.html'
    
    def post(self, request, *args, **kwargs):
        if not can_upload(request.user):
            return redirect('current_members')
            
        if 'file' not in request.FILES:
            messages.error(request, 'Please select a file to upload')
            return redirect('upload')
            
        file_obj = request.FILES['file']
        month = request.POST.get('month')
        year = request.POST.get('year')
        
        if not all([month, year]):
            messages.error(request, 'Please provide both month and year')
            return redirect('upload')
            
        try:
            print(f"\nProcessing upload for {month} {year}")
            print(f"File name: {file_obj.name}")
            
            # Read the file content
            file_content = file_obj.read()
            
            # Process current upload
            current_df = process_csv_file(io.StringIO(file_content.decode('utf-8')), month, year)
            
            # Save upload record with file content
            upload = MembershipUpload.objects.create(
                file_name=file_obj.name,
                month=month,
                year=year,
                file_content=file_content
            )
            
            # Get previous upload if exists
            previous_upload = MembershipUpload.objects.exclude(id=upload.id).order_by('-upload_date').first()
            
            if previous_upload:
                print(f"Found previous upload: {previous_upload.month} {previous_upload.year}")
                
                # Process previous month's data from stored content
                previous_df = process_csv_file(previous_upload.file_content, 
                                            previous_upload.month, 
                                            previous_upload.year)
                
                # Compare and get changes
                changes = compare_memberships(current_df, previous_df)
                
                # Save comparison report
                report = ComparisonReport.objects.create(
                    current_upload=upload,
                    previous_upload=previous_upload,
                    new_active_members=changes['new_active'],
                    new_free_members=changes['new_free'],
                    new_linked_members=changes['new_linked'],
                    new_leads=changes['new_leads'],
                    cancelled_members=changes['cancelled_members'],
                    status_changes=changes['status_changes'],
                    removed_members=changes['removed_members']
                )
                
                return redirect('report_detail', pk=report.pk)
            else:
                messages.info(request, 'First upload processed successfully. Upload another file to see comparisons.')
                return redirect('upload')
                
        except Exception as e:
            print(f"Error in upload view: {str(e)}")
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('upload')

class ReportHistoryView(LoginRequiredMixin, ListView):
    model = ComparisonReport
    template_name = 'reports/history.html'
    context_object_name = 'reports'
    ordering = ['-generated_date']

class ReportDetailView(LoginRequiredMixin, DetailView):
    model = ComparisonReport
    template_name = 'reports/comparison.html'
    context_object_name = 'report'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = self.get_object()
        context.update({
            'changes': {
                'new_active': report.new_active_members,
                'new_free': report.new_free_members,
                'new_linked': report.new_linked_members,
                'new_leads': report.new_leads,
                'cancelled_members': report.cancelled_members,
                'status_changes': report.status_changes,
                'removed_members': report.removed_members,
            },
            'current_month': report.current_upload.month,
            'current_year': report.current_upload.year,
            'previous_month': report.previous_upload.month,
            'previous_year': report.previous_upload.year,
        })
        return context

class CurrentMembersView(LoginRequiredMixin, TemplateView):
    template_name = 'reports/current_members.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get the latest upload
        latest_upload = MembershipUpload.objects.order_by('-upload_date').first()
        
        if latest_upload:
            # Read the CSV data
            df = process_csv_file(latest_upload.file_content, 
                                latest_upload.month, 
                                latest_upload.year)
            
            # Function to convert DataFrame records to dictionaries with address fields
            def to_member_records(df):
                records = []
                for _, row in df.iterrows():
                    record = {
                        'name': clean_for_json(row['name']),
                        'surname': clean_for_json(row['surname']),
                        'cell': clean_for_json(row['cell']),
                        'email': clean_for_json(row['email']),
                        'mandate_signed': format_date(row['mandate_signed']),
                        'complex_building': clean_for_json(row.get('Complex/Building', '')),
                        'street_number': clean_for_json(row.get('Street Number', '')),
                        'street': clean_for_json(row.get('Street', '')),
                        'suburb': clean_for_json(row.get('Suburb', '')),
                    }
                    records.append(record)
                return sorted(records, key=lambda x: (x['surname'].lower(), x['name'].lower()))
            
            # Categorize members
            active_members = df[df['status'] == 'ACTIVE']
            linked_members = df[df['status'] == 'LINKED']
            free_members = df[df['status'] == 'FREE']
            
            context.update({
                'active_members': to_member_records(active_members),
                'linked_members': to_member_records(linked_members),
                'free_members': to_member_records(free_members),
                'upload_month': latest_upload.month,
                'upload_year': latest_upload.year,
            })
        
        return context

@login_required
def export_report_pdf(request, pk):
    report = get_object_or_404(ComparisonReport, pk=pk)
    
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    filename = f"ERA_Membership_Report_{report.current_upload.month}_{report.current_upload.year}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Create the PDF object using ReportLab
    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=20,
        alignment=1  # Center alignment
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=10,
        spaceBefore=20,
        textColor=colors.darkgreen
    )
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        alignment=1  # Center alignment
    )
    
    # Add ERA Logo with proper aspect ratio
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'ERA Logo.png')
    if os.path.exists(logo_path):
        # Open image and get original dimensions
        with PILImage.open(logo_path) as img:
            width, height = img.size
            aspect = height / float(width)
        
        # Set width to 1.2 inches and calculate height to maintain aspect ratio
        img = Image(logo_path)
        img.drawWidth = 1.2 * inch
        img.drawHeight = 1.2 * inch * aspect
        img.hAlign = 'CENTER'
        elements.append(img)
    
    elements.append(Spacer(1, 12))
    
    # Title and metadata
    elements.append(Paragraph("Membership Comparison Report", title_style))
    elements.append(Paragraph(
        f"Comparing {report.current_upload.month} {report.current_upload.year} with {report.previous_upload.month} {report.previous_upload.year}",
        normal_style
    ))
    elements.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%Y-%m-%d')}",
        normal_style
    ))
    elements.append(Spacer(1, 20))
    
    def add_member_table(title, members, columns, column_widths=None):
        if members:
            elements.append(Paragraph(f"{title} ({len(members)})", heading_style))
            elements.append(Spacer(1, 8))
            
            # Prepare table data
            table_data = [columns]  # Header row
            for member in members:
                row = []
                for col in columns:
                    col_key = col.lower().replace(' ', '_')
                    value = member.get(col_key, '')
                    if col == 'Join Date' and 'mandate_signed' in member:
                        value = format_date(member['mandate_signed'])
                    row.append(value)
                table_data.append(row)
            
            # Create table with specified column widths
            if not column_widths:
                # Default column widths if none specified
                column_widths = [doc.width/len(columns)] * len(columns)
            
            table = Table(table_data, repeatRows=1, colWidths=column_widths)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWHEIGHT', (0, 0), (-1, -1), 16),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 12))
        else:
            elements.append(Paragraph(f"{title} (0)", heading_style))
            elements.append(Paragraph("No members found in this category.", normal_style))
            elements.append(Spacer(1, 12))
    
    # Add member tables with specific column widths
    page_width = doc.width
    
    # Column widths for different table types
    standard_widths = [
        page_width * 0.18,  # Name
        page_width * 0.18,  # Surname
        page_width * 0.17,  # Cell
        page_width * 0.32,  # Email
        page_width * 0.15,  # Status/Date
    ]
    
    status_change_widths = [
        page_width * 0.18,  # Name
        page_width * 0.18,  # Surname
        page_width * 0.17,  # Cell
        page_width * 0.23,  # Previous Status
        page_width * 0.24,  # New Status
    ]
    
    # Add member tables
    add_member_table(
        "New Active Members",
        report.new_active_members,
        ['Name', 'Surname', 'Cell', 'Email', 'Join Date'],
        standard_widths
    )
    
    add_member_table(
        "New Free Members",
        report.new_free_members,
        ['Name', 'Surname', 'Cell', 'Email', 'Status'],
        standard_widths
    )
    
    add_member_table(
        "New Linked Members",
        report.new_linked_members,
        ['Name', 'Surname', 'Cell', 'Email', 'Status'],
        standard_widths
    )
    
    add_member_table(
        "New Leads",
        report.new_leads,
        ['Name', 'Surname', 'Cell', 'Email', 'Status'],
        standard_widths
    )
    
    add_member_table(
        "Cancelled Members",
        report.cancelled_members,
        ['Name', 'Surname', 'Cell', 'Previous Status', 'New Status'],
        status_change_widths
    )
    
    add_member_table(
        "Other Status Changes",
        report.status_changes,
        ['Name', 'Surname', 'Cell', 'Previous Status', 'New Status'],
        status_change_widths
    )
    
    # Build PDF
    doc.build(elements)
    return response
