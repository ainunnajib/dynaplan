#!/usr/bin/env python3
"""Generate Dynaplan feature progress PDF."""
from fpdf import FPDF
from datetime import datetime

features = [
    ("F001", "User authentication & authorization", "Core Platform", "Done"),
    ("F002", "Workspace management", "Core Platform", "Done"),
    ("F003", "Model management", "Core Platform", "Done"),
    ("F004", "Dimensions & hierarchies", "Modeling Engine", "Done"),
    ("F005", "Modules & line items", "Modeling Engine", "Done"),
    ("F006", "Formula engine", "Modeling Engine", "Done"),
    ("F007", "Calculation dependency graph", "Modeling Engine", "Done"),
    ("F008", "Cell-level data storage", "Modeling Engine", "Done"),
    ("F009", "Time dimension & calendar", "Modeling Engine", "Done"),
    ("F010", "Versions (actuals/forecast/budget)", "Modeling Engine", "Done"),
    ("F011", "Grid view (spreadsheet UI)", "Grid & UX", "Done"),
    ("F012", "Pivot & filter controls", "Grid & UX", "Done"),
    ("F013", "Cell editing & input", "Grid & UX", "Done"),
    ("F014", "Module builder", "Grid & UX", "Done"),
    ("F015", "Dashboard builder", "Dashboards", "Done"),
    ("F016", "Charts & visualizations", "Dashboards", "Done"),
    ("F017", "Dashboard publishing & sharing", "Dashboards", "Done"),
    ("F018", "CSV/Excel import & export", "Data Integration", "Done"),
    ("F019", "REST API with API key auth", "Data Integration", "Done"),
    ("F020", "Actions & processes", "Data Integration", "Done"),
    ("F021", "Real-time collaboration", "Collaboration", "Done"),
    ("F022", "Comments & annotations", "Collaboration", "Done"),
    ("F023", "Audit trail & history", "Collaboration", "Done"),
    ("F024", "Scenario comparison", "Planning", "Done"),
    ("F025", "Top-down & bottom-up planning", "Planning", "Done"),
    ("F026", "Rolling forecasts", "Planning", "Done"),
    ("F027", "What-if analysis", "Planning", "Done"),
    ("F028", "Role-based access control", "Admin & Security", "Done"),
    ("F029", "SSO / SAML integration", "Admin & Security", "Done"),
    ("F030", "Model history & snapshots", "Admin & Security", "Done"),
    ("F031", "Calculation caching", "Performance", "Done"),
    ("F032", "Bulk data operations", "Performance", "Done"),
    ("F033", "Time ranges", "Modeling Engine", "Done"),
    ("F034", "List subsets & line item subsets", "Modeling Engine", "Done"),
    ("F035", "Selective access & DCA", "Admin & Security", "Done"),
    ("F036", "UX page types", "Grid & UX", "Done"),
    ("F037", "Management reporting", "Dashboards", "Done"),
    ("F038", "Workflow tasks & approvals", "Workflow", "Done"),
    ("F039", "Application Lifecycle Management", "Lifecycle", "Done"),
    ("F040", "CloudWorks scheduled integrations", "Data Integration", "Done"),
    ("F041", "Data Orchestrator pipelines", "Data Integration", "Done"),
    ("F042", "Transactional & chunked file APIs", "Data Integration", "Done"),
    ("F043", "SCIM user provisioning", "Admin & Security", "Done"),
    ("F044", "Engine profiles (Classic/Polaris)", "Performance", "Done"),
    ("F045", "Rust engine core - sparse block storage", "Rust Engine", "Done"),
    ("F046", "Rust formula engine", "Rust Engine", "Done"),
    ("F047", "Rust dependency graph", "Rust Engine", "Done"),
    ("F048", "Rust parallel calculation engine", "Rust Engine", "Done"),
    ("F049", "PyO3 bridge - Rust to Python", "Rust Engine", "Done"),
    ("F050", "Spread & aggregation in Rust", "Rust Engine", "Done"),
    ("F051", "Time functions (20 functions)", "Formula Language", "Done"),
    ("F052", "Lookup & cross-module functions", "Formula Language", "Done"),
    ("F053", "Text & conversion functions", "Formula Language", "Done"),
    ("F054", "Advanced aggregation & statistical", "Formula Language", "Done"),
    ("F055", "Summary method expansion", "Formula Language", "Done"),
    ("F056", "Numbered lists", "Model Structure", "Done"),
    ("F057", "Composite dimensions", "Model Structure", "Pending"),
    ("F058", "Saved views", "Model Structure", "Pending"),
    ("F059", "Applies-to normalization", "Model Structure", "Done"),
    ("F060", "Version dimension integration", "Model Structure", "Done"),
    ("F061", "Model calendar enhancements", "Model Structure", "Pending"),
    ("F062", "Background job executor", "Execution Runtime", "Done"),
    ("F063", "CloudWorks connector SDK", "Execution Runtime", "Done"),
    ("F064", "CloudWorks scheduler activation", "Execution Runtime", "Done"),
    ("F065", "Pipeline step execution runtime", "Execution Runtime", "Running"),
    ("F066", "ALM promotion engine", "Execution Runtime", "Done"),
    ("F067", "Data Hub (staging area)", "Data Integration", "Pending"),
    ("F068", "Bulk API CLI", "Data Integration", "Pending"),
    ("F069", "Workspace quotas & cell limits", "Scale & Security", "Done"),
    ("F070", "Data encryption at rest", "Scale & Security", "Pending"),
    ("F071", "IP allowlisting & cert auth", "Scale & Security", "Pending"),
    ("F072", "PostgreSQL migration", "Scale & Security", "Done"),
    ("F073", "New UX app builder", "Advanced UX", "Pending"),
    ("F074", "Conditional cell formatting", "Advanced UX", "Pending"),
    ("F075", "Grid performance at scale", "Advanced UX", "Pending"),
    ("F076", "Metrics & health dashboard", "Observability", "Pending"),
    ("F077", "Horizontal scaling", "Observability", "Pending"),
]

done_count = sum(1 for f in features if f[3] == "Done")
running_count = sum(1 for f in features if f[3] == "Running")
pending_count = sum(1 for f in features if f[3] == "Pending")
total = len(features)
pct = int(done_count / total * 100)


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(30, 30, 30)
        self.cell(0, 12, "Dynaplan - Feature Progress Report", new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}    |    {done_count}/{total} complete ({pct}%)    |    {running_count} running    |    {pending_count} pending", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(4)

        # Progress bar
        bar_w = 170
        bar_h = 6
        x_start = (self.w - bar_w) / 2
        # Background
        self.set_fill_color(230, 230, 230)
        self.rect(x_start, self.get_y(), bar_w, bar_h, "F")
        # Done portion
        done_w = bar_w * done_count / total
        self.set_fill_color(34, 197, 94)
        self.rect(x_start, self.get_y(), done_w, bar_h, "F")
        # Running portion
        if running_count > 0:
            run_w = bar_w * running_count / total
            self.set_fill_color(59, 130, 246)
            self.rect(x_start + done_w, self.get_y(), run_w, bar_h, "F")
        self.ln(bar_h + 6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Dynaplan - Open Source Anaplan Alternative    |    Page {self.page_no()}/{{nb}}", align="C")


pdf = PDF(orientation="P", unit="mm", format="A4")
pdf.alias_nb_pages()
pdf.set_auto_page_break(auto=True, margin=20)
pdf.add_page()

# Column widths
col_id = 14
col_name = 78
col_cat = 38
col_status = 20
total_w = col_id + col_name + col_cat + col_status
x_start = (pdf.w - total_w) / 2

# Table header
pdf.set_x(x_start)
pdf.set_font("Helvetica", "B", 8)
pdf.set_fill_color(45, 55, 72)
pdf.set_text_color(255, 255, 255)
pdf.cell(col_id, 7, " #", border=1, fill=True)
pdf.cell(col_name, 7, " Feature", border=1, fill=True)
pdf.cell(col_cat, 7, " Category", border=1, fill=True)
pdf.cell(col_status, 7, " Status", border=1, fill=True, align="C")
pdf.ln()

# Table rows
pdf.set_font("Helvetica", "", 7.5)
for i, (fid, name, cat, status) in enumerate(features):
    # Alternating row colors
    if i % 2 == 0:
        pdf.set_fill_color(248, 250, 252)
    else:
        pdf.set_fill_color(255, 255, 255)

    pdf.set_x(x_start)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(col_id, 6, f" {fid}", border="LB", fill=True)
    pdf.cell(col_name, 6, f" {name}", border="B", fill=True)

    # Category color coding
    cat_colors = {
        "Core Platform": (99, 102, 241),
        "Modeling Engine": (16, 185, 129),
        "Grid & UX": (245, 158, 11),
        "Dashboards": (236, 72, 153),
        "Data Integration": (14, 165, 233),
        "Collaboration": (168, 85, 247),
        "Planning": (34, 197, 94),
        "Admin & Security": (239, 68, 68),
        "Performance": (249, 115, 22),
        "Workflow": (20, 184, 166),
        "Lifecycle": (99, 102, 241),
        "Rust Engine": (234, 88, 12),
        "Formula Language": (16, 185, 129),
        "Model Structure": (59, 130, 246),
        "Execution Runtime": (168, 85, 247),
        "Scale & Security": (239, 68, 68),
        "Advanced UX": (245, 158, 11),
        "Observability": (107, 114, 128),
    }
    r, g, b = cat_colors.get(cat, (100, 100, 100))
    pdf.set_text_color(r, g, b)
    pdf.cell(col_cat, 6, f" {cat}", border="B", fill=True)

    # Status with icon
    if status == "Done":
        pdf.set_text_color(34, 197, 94)
        status_text = "Done"
    elif status == "Running":
        pdf.set_text_color(59, 130, 246)
        status_text = "Running"
    else:
        pdf.set_text_color(156, 163, 175)
        status_text = "Pending"
    pdf.cell(col_status, 6, status_text, border="RB", fill=True, align="C")
    pdf.ln()

# Summary section
pdf.ln(8)
pdf.set_font("Helvetica", "B", 11)
pdf.set_text_color(30, 30, 30)
pdf.cell(0, 8, "Summary by Category", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Helvetica", "", 9)

categories = {}
for fid, name, cat, status in features:
    if cat not in categories:
        categories[cat] = {"done": 0, "running": 0, "pending": 0, "total": 0}
    categories[cat]["total"] += 1
    if status == "Done":
        categories[cat]["done"] += 1
    elif status == "Running":
        categories[cat]["running"] += 1
    else:
        categories[cat]["pending"] += 1

for cat, counts in categories.items():
    r, g, b = cat_colors.get(cat, (100, 100, 100))
    pdf.set_text_color(r, g, b)
    pct_cat = int(counts["done"] / counts["total"] * 100)
    bar = "=" * (counts["done"] * 2) + "-" * ((counts["total"] - counts["done"]) * 2)
    pdf.cell(0, 5.5, f"  {cat}: {counts['done']}/{counts['total']} ({pct_cat}%)  [{bar}]", new_x="LMARGIN", new_y="NEXT")

output_path = "/Users/ainunnajib/dynaplan/dynaplan-progress.pdf"
pdf.output(output_path)
print(f"PDF written to {output_path}")
