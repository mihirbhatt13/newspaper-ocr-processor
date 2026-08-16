import os
from pathlib import Path
from fpdf import FPDF
from app.config import DIRS, ensure_directories

def create_sample_pdfs(page_count=7):
    """Generates 3 realistic sample newspaper PDF files (7 pages each = 21 pages total)."""
    ensure_directories()
    pdf_dir = DIRS["pdfs"]

    newspapers = [
        ("Dainik_Bhaskar_Hindi_Sample.pdf", page_count, "DAINIK BHASKAR - HINDI EDITION", [
            "EDUCATION NEWS: NEW SCHOLARSHIP SCHEME LAUNCHED FOR HIGHER EDUCATION.",
            "LOCAL NEWS: MUNICIPAL CORPORATION ANNOUNCES NEW INFRASTRUCTURE PROJECT.",
            "SPORTS UPDATE: STATE LEVEL CRICKET TOURNAMENT BEGINS THIS WEEKEND.",
            "BUSINESS SECTION: STOCKS REACH NEW HIGH AS MARKETS RALLY IN MUMBAI.",
            "TECHNOLOGY TODAY: DIGITAL LITERACY PROGRAM REACHES OVER 500 SCHOOLS.",
        ]),
        ("Gujarat_Samachar_Gujarati_Sample.pdf", page_count, "GUJARAT SAMACHAR - GUJARATI EDITION", [
            "EDUCATION BULLETIN: NEW SMART CLASSROOMS INAUGURATED ACROSS DISTRICT.",
            "STATE NEWS: AHMEDABAD METRO EXPANSION WORK MOVES TO PHASE TWO.",
            "WEATHER REPORT: HEAVY RAINFALL PREDICTED IN COASTAL REGIONS.",
            "BUSINESS NEWS: TEXTILE INDUSTRY SHOWS STRONG GROWTH THIS QUARTER.",
            "HEALTH CARE: FREE MEDICAL CHECKUP CAMP ORGANIZED IN SURAT.",
        ]),
        ("Chennai_Times_English_Sample.pdf", page_count, "CHENNAI TIMES - ENGLISH EDITION", [
            "EDUCATION FOCUS: UNIVERSITIES ANNOUNCE NEW SKILL DEVELOPMENT COURSES.",
            "CITY EDITION: TRAFFIC DIVERSIONS ANNOUNCED FOR COASTAL ROAD WORK.",
            "NATIONAL NEWS: RENEWABLE ENERGY CAPACITY EXPANDS NATIONWIDE.",
            "SCIENCE & TECH: LOCAL ISRO LAB INITIATES STUDENT SATELLITE PROGRAM.",
            "CULTURE: ANNUAL HERITAGE FESTIVAL CELEBRATES TRADITIONAL ARTS.",
        ])
    ]

    generated_files = []

    for filename, p_count, title, articles in newspapers:
        filepath = pdf_dir / filename
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        for p in range(1, p_count + 1):
            pdf.add_page()
            pdf.set_font("Arial", 'B', size=16)
            pdf.cell(0, 10, txt=f"{title} - PAGE {p}", ln=True, align='C')
            pdf.ln(5)
            
            pdf.set_font("Arial", size=11)
            pdf.cell(0, 8, txt=f"Date: 09 August 2026 | Edition: Daily Newspaper | Page {p} of {p_count}", ln=True, align='L')
            pdf.line(10, 30, 200, 30)
            pdf.ln(10)
            
            for article_idx, article in enumerate(articles, 1):
                pdf.set_font("Arial", 'B', size=12)
                pdf.cell(0, 8, txt=f"Article {article_idx}: {article[:35]}...", ln=True)
                pdf.set_font("Arial", size=10)
                
                content_text = (
                    f"{article} The government has emphasized the importance of quality learning "
                    f"and student support systems across all institutes. Further details released in today's official "
                    f"press conference confirm additional resource allocation for regional development projects. "
                    f"Experts have welcomed the move as a major step forward for institutional growth and public welfare."
                )
                pdf.multi_cell(0, 6, txt=content_text)
                pdf.ln(4)

        pdf.output(str(filepath))
        generated_files.append(filepath)
        print(f"Generated sample PDF: {filepath.name} ({p_count} pages)", flush=True)

    return generated_files

if __name__ == "__main__":
    create_sample_pdfs()
