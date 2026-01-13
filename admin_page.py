import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date

def show_admin_dashboard(df):
    """
    Display the Manager/Admin Dashboard with KPIs, charts, and detailed view.
    
    Args:
        df: DataFrame containing ticket data with columns:
            - Date, Agent_Name, Status, Issue_Category, etc.
    """
    st.title("🔐 Manager Dashboard")
    st.markdown("---")
    
    # Store original dataframe
    df_original = df.copy()
    
    # Ensure Date and Created_At are datetime for filtering
    # Use dayfirst=False for MM/DD/YYYY format (US format)
    date_column = None
    if 'Created_At' in df.columns:
        df['Created_At'] = pd.to_datetime(df['Created_At'], dayfirst=False, errors='coerce')
        date_column = 'Created_At'
    elif 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=False, errors='coerce')
        date_column = 'Date'
    
    # Debug: Show detected date range
    if date_column:
        valid_dates = df[date_column].dropna()
        if len(valid_dates) > 0:
            min_date = valid_dates.min()
            max_date = valid_dates.max()
            
            # Debug info - show what system detects
            min_str = min_date.strftime('%Y-%m-%d') if pd.notna(min_date) else 'NaT'
            max_str = max_date.strftime('%Y-%m-%d') if pd.notna(max_date) else 'NaT'
            st.warning(f"🔍 System detects data range: {min_str} to {max_str}")
            
            # Calculate default date range from actual data
            if pd.notna(min_date) and pd.notna(max_date):
                data_start = min_date.date()
                data_end = max_date.date()
            else:
                # Fallback to current month if dates are invalid
                today = date.today()
                data_start = date(today.year, today.month, 1)
                data_end = today
        else:
            st.warning("⚠️ No valid dates found in data! All dates are NaT.")
            today = date.today()
            data_start = date(today.year, today.month, 1)
            data_end = today
    else:
        # No date column found
        st.warning("⚠️ No date column found in data!")
        today = date.today()
        data_start = date(today.year, today.month, 1)
        data_end = today
    
    # Sidebar Filters Section
    with st.sidebar:
        st.markdown("---")
        st.subheader("🔍 Filter Options")
        
        # Date Range Picker
        # Default to actual data range (min to max) instead of current month
        date_range = st.date_input(
            "📅 Date Range",
            value=(data_start, data_end),
            min_value=None,
            max_value=date.today(),
            help="Select start and end date for filtering tickets"
        )
        
        # Search Keyword Input
        search_keyword = st.text_input(
            "🔎 Search Keyword",
            placeholder="Search in Note or Issue Category...",
            help="Case-insensitive search in Note and Issue_Category fields"
        )
        
        st.markdown("---")
    
    # Apply Date Range Filter
    df_filtered = df.copy()
    
    if date_column:
        try:
            # Handle date_range - it can be a tuple, list, or single date
            if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
                # Date range selected
                start_date = pd.to_datetime(date_range[0])
                end_date = pd.to_datetime(date_range[1])
                
                # Set end_date to end of day for inclusive filtering
                end_date = end_date + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
                
                # Filter by date range
                if date_column == 'Created_At':
                    df_filtered = df_filtered[
                        (df_filtered['Created_At'] >= start_date) & 
                        (df_filtered['Created_At'] <= end_date)
                    ]
                elif date_column == 'Date':
                    df_filtered = df_filtered[
                        (df_filtered['Date'] >= start_date) & 
                        (df_filtered['Date'] <= end_date)
                    ]
            elif isinstance(date_range, (tuple, list)) and len(date_range) == 1:
                # Single date selected - filter for that day only
                selected_date = pd.to_datetime(date_range[0])
                start_of_day = selected_date
                end_of_day = selected_date + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
                
                if date_column == 'Created_At':
                    df_filtered = df_filtered[
                        (df_filtered['Created_At'] >= start_of_day) & 
                        (df_filtered['Created_At'] <= end_of_day)
                    ]
                elif date_column == 'Date':
                    df_filtered = df_filtered[
                        (df_filtered['Date'] >= start_of_day) & 
                        (df_filtered['Date'] <= end_of_day)
                    ]
        except Exception as e:
            # If date filtering fails, use all data
            st.warning(f"⚠️ Date filter error: {str(e)}. Showing all data.")
    
    # Apply Search Keyword Filter
    if search_keyword and search_keyword.strip():
        search_term = search_keyword.strip().lower()
        
        # Search in Note and Issue_Category columns
        mask = pd.Series([False] * len(df_filtered))
        
        if 'Note' in df_filtered.columns:
            mask = mask | df_filtered['Note'].astype(str).str.lower().str.contains(search_term, na=False)
        
        if 'Issue_Category' in df_filtered.columns:
            mask = mask | df_filtered['Issue_Category'].astype(str).str.lower().str.contains(search_term, na=False)
        
        df_filtered = df_filtered[mask]
    
    # Check if filtered data is empty
    if len(df_filtered) == 0:
        st.warning("⚠️ No tickets match the selected filters. Please adjust your filter criteria.")
        st.info("💡 Try expanding the date range or removing the search keyword.")
        return
    
    # Show filter summary
    filter_info = []
    try:
        if date_column and isinstance(date_range, (tuple, list)) and len(date_range) == 2:
            filter_info.append(f"📅 {date_range[0].strftime('%Y-%m-%d')} to {date_range[1].strftime('%Y-%m-%d')}")
        elif date_column and isinstance(date_range, (tuple, list)) and len(date_range) == 1:
            filter_info.append(f"📅 {date_range[0].strftime('%Y-%m-%d')}")
    except:
        pass  # Skip date info if formatting fails
    
    if search_keyword and search_keyword.strip():
        filter_info.append(f"🔎 '{search_keyword}'")
    
    if filter_info:
        st.info(" | ".join(filter_info) + f" → Showing {len(df_filtered)} of {len(df_original)} tickets")
    
    # Calculate KPIs using filtered data
    total_tickets_filtered = len(df_filtered)
    pending_issues = len(df_filtered[df_filtered['Status'] != 'Done']) if 'Status' in df_filtered.columns else 0
    
    # Calculate work hours (approximate: assume 15 minutes per ticket)
    # Or use Support_Time if available to calculate duration
    work_hours = 0
    if 'Support_Time' in df_filtered.columns:
        # Try to calculate from Support_Time if available
        support_times = df_filtered['Support_Time'].dropna()
        if len(support_times) > 0:
            # Approximate: count tickets as work units (15 min per ticket)
            work_hours = round(len(support_times) * 0.25, 1)
    else:
        # Fallback: use ticket count as proxy
        work_hours = round(total_tickets_filtered * 0.25, 1)
    
    # Active staff count (unique agents with tickets in filtered data)
    active_staff_count = df_filtered['Agent_Name'].nunique() if 'Agent_Name' in df_filtered.columns else 0
    
    # Calculate resolved count
    resolved_count = total_tickets_filtered - pending_issues
    
    # KPI Row
    st.subheader("📊 Key Performance Indicators")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Tickets (Selected Period)",
            value=total_tickets_filtered,
            delta=f"{len(df_original)} all time" if len(df_filtered) < len(df_original) else None,
            delta_color="off"
        )
    
    with col2:
        st.metric(
            label="Pending Issues",
            value=pending_issues,
            delta=f"{resolved_count} resolved" if resolved_count > 0 else None,
            delta_color="inverse"
        )
    
    with col3:
        st.metric(
            label="Total Work Hours",
            value=f"{work_hours}",
            delta="Estimated",
            delta_color="off"
        )
    
    with col4:
        st.metric(
            label="Active Staff",
            value=active_staff_count,
            delta="Currently working",
            delta_color="off"
        )
    
    st.markdown("---")
    
    # Charts Section
    st.subheader("📈 Analytics & Insights")
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("#### 📊 Tickets per Staff")
        if 'Agent_Name' in df_filtered.columns and len(df_filtered) > 0:
            # Count tickets per staff member (using filtered data)
            staff_counts = df_filtered['Agent_Name'].value_counts().head(10)  # Top 10
            
            if len(staff_counts) > 0:
                fig_staff = px.bar(
                    x=staff_counts.values,
                    y=staff_counts.index,
                    orientation='h',
                    labels={'x': 'Number of Tickets', 'y': 'Staff Member'},
                    color=staff_counts.values,
                    color_continuous_scale='Blues',
                    title="Who is working the most?"
                )
                fig_staff.update_layout(
                    showlegend=False,
                    height=400,
                    yaxis={'categoryorder': 'total ascending'}
                )
                st.plotly_chart(fig_staff, use_container_width=True)
            else:
                st.info("No staff data available")
        else:
            st.info("No staff data available")
    
    with col_chart2:
        st.markdown("#### 🥧 Issue Type Distribution")
        if 'Issue_Category' in df_filtered.columns and len(df_filtered) > 0:
            # Count issue types (using filtered data)
            issue_counts = df_filtered['Issue_Category'].value_counts()
            
            if len(issue_counts) > 0:
                fig_issues = px.pie(
                    values=issue_counts.values,
                    names=issue_counts.index,
                    title="Why are customers calling?",
                    hole=0.4
                )
                fig_issues.update_traces(
                    textposition='inside',
                    textinfo='percent+label'
                )
                fig_issues.update_layout(height=400)
                st.plotly_chart(fig_issues, use_container_width=True)
            else:
                st.info("No issue category data available")
        else:
            st.info("No issue category data available")
    
    st.markdown("---")
    
    # Detailed View with Additional Filters
    st.subheader("📋 Detailed Ticket View")
    
    # Additional filters for detailed view (Staff and Status)
    filter_col1, filter_col2 = st.columns(2)
    
    with filter_col1:
        # Staff Name filter (from filtered data)
        if 'Agent_Name' in df_filtered.columns:
            staff_list = ['All'] + sorted(df_filtered['Agent_Name'].dropna().unique().tolist())
            selected_staff = st.selectbox(
                "Filter by Staff Name:",
                options=staff_list,
                index=0
            )
        else:
            selected_staff = 'All'
    
    with filter_col2:
        # Status filter (from filtered data)
        if 'Status' in df_filtered.columns:
            status_list = ['All'] + sorted(df_filtered['Status'].dropna().unique().tolist())
            selected_status = st.selectbox(
                "Filter by Status:",
                options=status_list,
                index=0
            )
        else:
            selected_status = 'All'
    
    # Apply additional filters to already filtered data
    df_display = df_filtered.copy()
    
    if selected_staff != 'All' and 'Agent_Name' in df_display.columns:
        df_display = df_display[df_display['Agent_Name'] == selected_staff]
    
    if selected_status != 'All' and 'Status' in df_display.columns:
        df_display = df_display[df_display['Status'] == selected_status]
    
    # Display filtered dataframe
    if len(df_display) > 0:
        st.success(f"Showing {len(df_display)} ticket(s)")
        
        # Reorder columns for better visibility
        priority_columns = ['Date', 'Agent_Name', 'Salon_Name', 'CID', 'Phone', 
                          'Issue_Category', 'Status', 'Note']
        other_columns = [col for col in df_display.columns if col not in priority_columns]
        column_order = [col for col in priority_columns if col in df_display.columns] + other_columns
        df_display = df_display[column_order]
        
        # Format Date column for display (MM/DD/YYYY format)
        # Sort by datetime first, then format for display
        if 'Date' in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display['Date']):
            # Sort by Date (datetime) before formatting
            df_display = df_display.sort_values('Date', ascending=False, na_position='last')
            # Format Date column to MM/DD/YYYY string for display
            df_display['Date'] = df_display['Date'].apply(
                lambda x: x.strftime('%m/%d/%Y') if pd.notna(x) else ''
            )
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            height=400
        )
        
        # Export option
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Filtered Data (CSV)",
            data=csv,
            file_name=f"admin_dashboard_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.warning("No tickets match the selected filters.")
